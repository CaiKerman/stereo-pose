"""Native reference form adapter. Existing CSV validator/fitter/save remains owner."""
from __future__ import annotations

import csv
import os
import tempfile
import time
from pathlib import Path

from stereo_pose.app.desktop import ImagePair, initial_size


FIELDS = ('dictionary','id','feature_type','X_mm','Y_mm','Z_mm')


def load_form_rows(reference):
    with Path(reference).open(newline='',encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    return [{name:row.get(name,'') for name in FIELDS} for row in rows]


def save_form_rows(reference, rows, *, zero=False):
    """Atomic reference editing, with old contents retained on input/write failure.

    No geometry validation is replaced: read_references and match_features still
    run inside the original world workflow after this presentation-only save.
    Unfilled detected templates may be omitted. Partial XYZ rows are an error.
    Zero selects the first data row, matching the existing zero-only semantics.
    """
    selected=list(rows[:1] if zero else rows)
    cleaned=[]
    for row in selected:
        values=[str(row.get(k,'')).strip() for k in ('X_mm','Y_mm','Z_mm')]
        if not any(values) and not zero:
            continue
        if not all(values):
            raise ValueError(f'编号 {row.get("id", "?")} 的 X、Y、Z 都需要填写；只改原点通常填 0, 0, 0。')
        cleaned.append({name:str(row.get(name,'')).strip() for name in FIELDS})
    if not cleaned:
        raise ValueError('请至少填写一个参考点；完整坐标系至少需要三个不共线点。')
    path=Path(reference)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(cleaned)
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


class WorldForm:
    def __init__(self, desktop, reference, left, right, dictionary, name):
        self.desktop=desktop
        self.tk,self.ttk=desktop.tk,desktop.ttk
        self.reference=reference
        self.desktop_dictionary=dictionary
        self.rows=load_form_rows(reference)
        self.shared=set(left)&set(right)
        self.pending=255;self.closed=False;self.last_zero=False;self.last_report=None
        self.requested_fit=False
        self.loading_entries=False
        self.root=self.tk.Toplevel(desktop.root)
        self.root.title('设置坐标系与原点 · 当前画面已冻结')
        width,height=initial_size(desktop.root.winfo_screenwidth(),desktop.root.winfo_screenheight(),desktop.scale)
        self.root.geometry(f'{width}x{height}')
        self.root.minsize(min(width,round(520*desktop.scale)),min(height,round(440*desktop.scale)))
        self.root.resizable(True,True);self.root.transient(desktop.root)
        self.root.protocol('WM_DELETE_WINDOW',self.cancel)
        self.root.grab_set()
        self.root.columnconfigure(0,weight=1);self.root.rowconfigure(2,weight=1)
        self.title=self.ttk.Label(self.root,text='1 选择模式  →  2 填写实测坐标  →  3 预览方向  →  4 保存',padding=12)
        self.title.grid(row=0,column=0,sticky='ew')
        self.top=self.ttk.Frame(self.root,padding=(12,0));self.top.grid(row=1,column=0,sticky='ew')
        self.zero=self.tk.BooleanVar(value=False)
        self.ttk.Radiobutton(self.top,text='完整坐标系：设原点与轴向',variable=self.zero,value=False,command=self.change_mode).grid(row=0,column=0,sticky='w')
        self.ttk.Radiobutton(self.top,text='只改原点：保留当前轴向',variable=self.zero,value=True,command=self.change_mode).grid(row=1,column=0,sticky='w')
        self.name=self.tk.StringVar(value=name)
        self.ttk.Label(self.top,text='坐标名称：').grid(row=0,column=1,sticky='e',padx=(16,0))
        self.name_entry=self.ttk.Entry(self.top,textvariable=self.name,width=18)
        self.name_entry.grid(row=0,column=2,sticky='ew')
        self.name_entry.bind('<Return>',lambda event:self.root.focus_set())
        self.top.columnconfigure(2,weight=1)
        self.panes=self.ttk.Panedwindow(self.root,orient='vertical');self.panes.grid(row=2,column=0,sticky='nsew',padx=12,pady=8)
        self.pair=ImagePair(self.panes,self.tk,self.ttk);self.panes.add(self.pair.frame,weight=2)
        editor=self.ttk.Frame(self.panes);editor.columnconfigure(0,weight=1);editor.rowconfigure(1,weight=1)
        self.panes.add(editor,weight=3)
        self.guidance=self.ttk.Label(editor,text='选择一行，在下方填写 X / Y / Z（毫米），点击「更新此点」。至少三个不共线点；只改原点使用第一行。',wraplength=900,padding=(0,6))
        self.guidance.grid(row=0,column=0,columnspan=2,sticky='ew')
        columns=('id','feature_type','X_mm','Y_mm','Z_mm','seen')
        self.tree=self.ttk.Treeview(editor,columns=columns,show='headings',height=4,selectmode='browse')
        for key,label in zip(columns,['编号','特征点','X / mm','Y / mm','Z / mm','双目识别']):
            self.tree.heading(key,text=label);self.tree.column(key,width=100,minwidth=70)
        self.tree.grid(row=1,column=0,sticky='nsew')
        bar=self.ttk.Scrollbar(editor,orient='vertical',command=self.tree.yview);bar.grid(row=1,column=1,sticky='ns')
        horizontal=self.ttk.Scrollbar(editor,orient='horizontal',command=self.tree.xview);horizontal.grid(row=2,column=0,sticky='ew')
        self.tree.configure(yscrollcommand=bar.set,xscrollcommand=horizontal.set)
        self.tree.bind('<<TreeviewSelect>>',self.select_row)
        self.input=self.ttk.Frame(editor,padding=(0,6));self.input.grid(row=3,column=0,columnspan=2,sticky='ew')
        self.entries={}
        for i,(key,label) in enumerate([('X_mm','X'),('Y_mm','Y'),('Z_mm','Z')]):
            self.ttk.Label(self.input,text=label).grid(row=0,column=i*2,sticky='e',padx=3)
            variable=self.tk.StringVar()
            entry=self.ttk.Entry(self.input,textvariable=variable,width=9)
            entry.grid(row=0,column=i*2+1,sticky='ew')
            entry.bind('<Return>',lambda event:self.update_row())
            self.input.columnconfigure(i*2+1,weight=1);self.entries[key]=variable
        self.ttk.Button(self.input,text='更新此点',command=self.update_row).grid(row=1,column=0,columnspan=2,sticky='w',pady=4)
        self.ttk.Button(self.input,text='此点作为零点',command=self.set_origin).grid(row=1,column=2,columnspan=2,sticky='w')
        self.ttk.Button(self.input,text='加入已识别图码',command=lambda:self.add_detected(dictionary)).grid(row=1,column=4,columnspan=2,sticky='w')
        bottom=self.ttk.Frame(self.root,padding=12);bottom.grid(row=3,column=0,sticky='ew');bottom.columnconfigure(0,weight=1)
        self.message=self.ttk.Label(bottom,text='',wraplength=900,justify='left');self.message.grid(row=0,column=0,columnspan=4,sticky='ew',pady=(0,6))
        self.up=self.tk.BooleanVar(value=False)
        self.up_button=self.ttk.Checkbutton(bottom,text='已确认预览的 +Z 在物理上向上',variable=self.up,command=lambda:self.offer(ord('u')))
        self.up_button.grid(row=1,column=0,columnspan=4,sticky='w')
        self.ttk.Button(bottom,text='计算并预览  R',command=self.fit).grid(row=2,column=0,sticky='w',pady=(8,0))
        self.save_button=self.ttk.Button(bottom,text='保存并启用',command=lambda:self.offer(13),state='disabled')
        self.save_button.grid(row=2,column=1,padx=6,pady=(8,0))
        self.ttk.Button(bottom,text='取消 / 重新拍摄',command=self.cancel).grid(row=2,column=2,pady=(8,0))
        self.root.bind('<KeyPress>',self.keyboard)
        self.root.bind('<Configure>',self.reflow)
        for variable in self.entries.values():
            variable.trace_add('write',self.coordinates_edited)
        self.refresh_rows()
        self.root.update_idletasks();self.panes.sashpos(0,int(height*.34))

    def reflow(self,event=None):
        width=max(200,self.root.winfo_width()-30)
        self.guidance.configure(wraplength=width);self.message.configure(wraplength=width)

    def refresh_rows(self):
        for item in self.tree.get_children():self.tree.delete(item)
        for i,row in enumerate(self.rows):
            detected=self.recognized(row)
            self.tree.insert('','end',iid=str(i),values=(*[row[k] for k in ('id','feature_type','X_mm','Y_mm','Z_mm')], '成功' if detected else '未识别'))
        if self.rows:self.tree.selection_set('0');self.select_row()

    def recognized(self,row):
        try:return row['dictionary']==self.desktop_dictionary and int(row['id']) in self.shared
        except ValueError:return False

    def select_row(self,event=None):
        selection=self.tree.selection()
        if not selection:return
        row=self.rows[int(selection[0])]
        self.loading_entries=True
        try:
            for key,var in self.entries.items():var.set(row[key])
        finally:self.loading_entries=False

    def coordinates_edited(self,*args):
        if not self.loading_entries:self.invalidate()

    def invalidate(self):
        self.up.set(False);self.save_button.configure(state='disabled')
        if self.pending not in (ord('z'),27):self.pending=255
        self.dirty=True

    def update_row(self):
        selection=self.tree.selection()
        if not selection:return
        index=int(selection[0]);row=self.rows[index]
        for key,var in self.entries.items():row[key]=var.get().strip()
        self.tree.item(str(index),values=(*[row[k] for k in ('id','feature_type','X_mm','Y_mm','Z_mm')], '成功' if self.recognized(row) else '未识别'))
        self.invalidate()
        self.message.configure(text='参考点已更新。请点击「计算并预览」；未经重新计算不能保存。')

    def set_origin(self):
        for var in self.entries.values():var.set('0')
        self.update_row()
        if self.zero.get() and self.tree.selection():
            index=int(self.tree.selection()[0]);self.rows.insert(0,self.rows.pop(index));self.refresh_rows()

    def add_detected(self,dictionary):
        existing={(r['dictionary'],r['id']) for r in self.rows}
        for i in sorted(self.shared):
            if (dictionary,str(i)) not in existing:self.rows.append(dict(zip(FIELDS,[dictionary,str(i),'center','','',''])))
        self.refresh_rows();self.invalidate()

    def offer(self,key):
        if self.pending==255:self.pending=key

    def change_mode(self):
        self.offer(ord('z'));self.invalidate();self.pending=ord('z')

    def fit(self):
        if bool(self.zero.get()) != bool(self.last_zero):
            # A mode click and fit can arrive in one event batch. Deliver the
            # existing Z handler first, then fit on the next UI iteration.
            self.pending=ord('z');self.requested_fit=True;return
        self.update_row()
        try:save_form_rows(self.reference,self.rows,zero=self.zero.get())
        except (OSError,ValueError) as error:
            self.message.configure(text=str(error));return
        self.dirty=False;self.offer(ord('r'))

    def cancel(self):
        self.closed=True;self.pending=27

    def keyboard(self,event):
        if event.keysym=='Escape':self.cancel();return 'break'
        if event.widget.winfo_class() in ('Entry','TEntry','Text','TCombobox'):
            return
        key=event.char.lower()
        if key=='r':self.fit()
        elif key=='z':self.zero.set(not self.zero.get());self.change_mode()
        elif key=='u':self.up.set(not self.up.get());self.offer(ord('u'))
        elif key=='n':self.name_entry.focus_set();self.name_entry.selection_range(0,'end')
        elif event.keysym=='Return':self.offer(13)
        elif key=='q':self.cancel()
        else:return
        return 'break'

    def show(self,images,*,zero,up,candidate,report,error):
        self.last_zero=zero
        # The original loop owns whether a candidate exists and is confirmed.
        valid=candidate is not None and not getattr(self,'dirty',False)
        self.save_button.configure(state='normal' if valid and (zero or up) else 'disabled')
        self.up_button.configure(state='disabled' if zero or not valid else 'normal')
        self.up.set(up)
        if valid:
            if zero:text='原点预览完成，轴向保持不变。可保存并启用。'
            else:text=f'预览完成：拟合残差均方根 {report.get("rms_mm", "—")} mm，最大 {report.get("max_mm", "—")} mm。检查方向，再确认 +Z 向上。'
        else:text='填写实测坐标后点击「计算并预览」。完整模式至少三点不共线；原点模式使用第一行。'
        if error not in ('Enter real XYZ in CSV, save it, then R=fit','Review axes/residuals. U confirms world-up; ENTER saves+activates.','Mode changed; press R to fit'):
            advice=('参考点至少三个，并且不能排成一条直线。' if 'collinear' in str(error) else
                    '左右画面必须识别到对应编号；核对图码字典，必要时取消并重新冻结画面。' if 'missing/mismatched' in str(error) else
                    '参考点对齐误差过大；核对编号、实测坐标、毫米单位和相机安装。' if 'registration residual' in str(error) else
                    '检查参考点填写与预览步骤。')
            if error:text+='\n'+advice+'\n'+str(error)
        if getattr(self,'dirty',False):text='参考点已修改，请重新计算并预览，不能保存旧结果。'
        self.message.configure(text=text)
        self.pair.render(images)
        try:self.root.update()
        except self.tk.TclError:self.closed=True
        key=self.pending;self.pending=255
        if key==255 and self.requested_fit:
            self.requested_fit=False;self.fit();key=self.pending;self.pending=255
        if key==13 and not self.name.get().strip():
            self.message.configure(text='请填写坐标名称。');return 255
        if key==255 and not self.closed:time.sleep(.02)
        return 27 if self.closed or self.desktop.closed else key

    def close(self):
        if not hasattr(self,'root'):return
        try:self.root.grab_release();self.root.destroy()
        except self.tk.TclError:pass
