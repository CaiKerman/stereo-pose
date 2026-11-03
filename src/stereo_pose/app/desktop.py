"""Optional Tk presentation. Buttons return original keys to the unchanged handlers.

No camera/inference/triangulation, no file persistence, and no background thread.
The existing processing loop owns events and resources; a missing Tk falls back
to HighGUI. Only resized COPIES reach the display, never the measurement input.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from collections import deque

import cv2

from stereo_pose.app.presentation import PendingAction, fit_size, initial_size


HELP = '''日常使用
1. 选择同一对物理摄像头，保持安装位置不变。
2. 已有有效双目标定时，可直接读取坐标。
3. 「坐标与原点」设置你自己的零点和轴向。
4. 「开始录制」按需记录坐标；再次点击停止。

双目标定
完整棋盘必须同时出现在左右画面中。每换一个明显不同的姿态，保持静止，程序自动采样。
同一姿态不重复采样。手动采样仍要求双目识别和面积合格。
样本数够用后可计算；覆盖评分不是精度保证。返回测量不会替换已有标定。

坐标与原点
「只改原点」使用一个图码参考点，保持现有轴向。
「完整坐标系」至少三个不共线、具有实测 XYZ 的图码特征点；推荐更多分散的点。
世界设置冻结当前图像。图码不完整时取消、摆好，再进入。
默认 +Z 向上依赖相机水平正立安装；零点平移不能建立重力方向。

窗口与快捷键
拖动边框或最大化；拖动画面与数据之间的分隔条调整比例。窄窗口左右画面自动上下排列。
坐标表和诊断区都可滚动。只有「有效」坐标可当测量值；候选和缺失显示 —。
旧快捷键全部保留：C 标定，W 坐标，T 录制，F 平滑，M 详情，S 快照，P 保留标定，
D 终端诊断，V 棋盘检查，G 清理，Q / Esc 退出；标定内 SPACE 采样，R 求解，X 丢弃。
双眼中点是检测眼点的中点，不是注视点；显示一位小数不等于毫米级准确度。
'''


def desktop_available():
    return os.name == 'nt' or sys.platform == 'darwin' or bool(os.environ.get('DISPLAY'))


def enable_dpi_awareness():
    if os.name != 'nt':
        return
    try:
        import ctypes
        # Must precede the first Tk/HighGUI window. Ignore an already-set context.
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass


def work_area(root=None):
    if os.name == 'nt':
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
                return rect.right-rect.left, rect.bottom-rect.top
        except (AttributeError, OSError):
            pass
    if root is not None:
        return root.winfo_screenwidth(), root.winfo_screenheight()
    return 1280, 720


def configure_fonts(root):
    from tkinter import font
    families={str(name).lower():str(name) for name in font.families(root)}
    preferred=('Microsoft YaHei UI','Microsoft YaHei','PingFang SC','Noto Sans CJK SC',
               'WenQuanYi Zen Hei','WenQuanYi Bitmap Song')
    family=next((families[name.lower()] for name in preferred if name.lower() in families),None)
    if family is not None:
        for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont'):
            font.nametofont(name,root=root).configure(family=family)
    heading=font.nametofont('TkDefaultFont',root=root).copy()
    heading.configure(size=16,weight='bold')
    return heading


def configure_highgui(name, shape):
    """Make compatibility/picker windows resizable without opening tests' GUI."""
    if not desktop_available():
        return False
    enable_dpi_awareness()
    cv2.namedWindow(name, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    width, height = initial_size(*work_area())
    width, height = fit_size((shape[1], shape[0]), (width, height))
    cv2.resizeWindow(name, width, height)
    return True


class HighGuiDisplay:
    native = False
    def __init__(self, name='Stereo Pose 3D'):
        self.name = name
        self.initialized = False
        self.check_close = False

    def show(self, canvas, *, pair=None, view=None):
        if not self.initialized:
            self.check_close = configure_highgui(self.name, canvas.shape)
            self.initialized = True
        cv2.imshow(self.name, canvas)
        key = cv2.waitKey(1) & 0xff
        if self.check_close:
            try:
                if cv2.getWindowProperty(self.name, cv2.WND_PROP_VISIBLE) < 1:
                    return ord('q')
            except cv2.error:
                return ord('q')
        return key

    def notify(self, message):
        print('[ui]', message)

    def close(self):
        if self.initialized:
            try:
                cv2.destroyWindow(self.name)
            except cv2.error:
                pass


def encode_tk_png(frame):
    """Encode OpenCV BGR preview to portable PNG bytes for Tk PhotoImage.

    Base64-encoded PNG avoids the binary PPM path that may render blank with
    some Windows/Tk builds; no third-party GUI dependencies are needed.
    """
    ok, encoded = cv2.imencode('.png', frame, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    if not ok:
        raise RuntimeError('could not encode camera preview as PNG')
    return base64.b64encode(encoded.tobytes())


class ImagePair:
    """Aspect-preserving live/frozen pair; only display copies are resized."""
    def __init__(self, parent, tk, ttk):
        self.tk = tk
        # Without a requested height the video pane can start at 1 pixel on
        # Windows Tk, even though the image renderer receives live frames.
        self.frame = ttk.Frame(parent, height=180)
        self.images = None
        self.photos = [None, None]
        self.rendered_bounds = [None, None]
        self.cells = []
        self.labels = []
        for name in ['左相机 / LEFT', '右相机 / RIGHT']:
            cell = ttk.Frame(self.frame)
            cell.pack_propagate(False)
            ttk.Label(cell, text=name).pack(anchor='w', padx=8, pady=(4,0))
            label = tk.Label(cell, background='#101827', borderwidth=0)
            label.pack(fill='both', expand=True)
            self.cells.append(cell)
            self.labels.append(label)
            index = len(self.labels) - 1
            label.bind('<Configure>', lambda event, i=index: self._on_label_resize(i, event))
        self.frame.bind('<Configure>', self._reflow)

    def _reflow(self, event=None):
        wide = self.frame.winfo_width() >= 760 * self.frame.winfo_fpixels('1i') / 96
        for i, cell in enumerate(self.cells):
            cell.grid(row=0 if wide else i, column=i if wide else 0, sticky='nsew', padx=2)
        for i in range(2):
            self.frame.columnconfigure(i, weight=1 if wide or i==0 else 0)
            self.frame.rowconfigure(i, weight=1 if not wide or i==0 else 0)
        if self.images is not None:
            self.render(self.images)

    def _on_label_resize(self, index, event):
        # Parent layout can complete before the video label has real dimensions.
        # Draw the latest image as soon as the label becomes visible.
        bounds = (event.width, event.height)
        if self.images is not None and min(bounds) >= 2 and bounds != self.rendered_bounds[index]:
            self._render_one(index, self.images[index])

    def _render_one(self, index, image):
        label = self.labels[index]
        bounds = (label.winfo_width(), label.winfo_height())
        if min(bounds) < 2:
            return
        size = fit_size((image.shape[1], image.shape[0]), bounds)
        scaled = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
        photo = self.tk.PhotoImage(master=label, data=encode_tk_png(scaled), format='png')
        label.configure(image=photo)
        self.photos[index] = photo  # Tk needs a live Python reference.
        self.rendered_bounds[index] = bounds

    def render(self, images):
        self.images = images
        for index, image in enumerate(images):
            self._render_one(index, image)


def scroll_text(parent, tk, ttk, *, editable=False):
    frame = ttk.Frame(parent)
    frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1)
    text = tk.Text(frame,wrap='word',height=6,borderwidth=0,padx=12,pady=10,
                   background='#f6f8fc',font='TkDefaultFont',state='normal' if editable else 'disabled')
    bar = ttk.Scrollbar(frame,orient='vertical',command=text.yview)
    text.configure(yscrollcommand=bar.set)
    text.grid(row=0,column=0,sticky='nsew');bar.grid(row=0,column=1,sticky='ns')
    return frame,text


def set_text(widget, value):
    if getattr(widget,'_last_value',None) == value:
        return
    widget.configure(state='normal');widget.delete('1.0','end');widget.insert('1.0',value)
    widget.configure(state='disabled');widget._last_value=value


class DesktopDisplay:
    native = True
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        self.tk,self.ttk = tk,ttk
        self.root = tk.Tk()
        self.heading_font=configure_fonts(self.root)
        self.root.title('Stereo Pose · 双目三维测量')
        self.root.resizable(True,True)
        self.scale=max(.75,min(3.,self.root.winfo_fpixels('1i')/96))
        width,height = initial_size(*work_area(self.root),self.scale)
        self.root.geometry(f'{width}x{height}')
        self.root.minsize(min(round(520*self.scale),width),min(round(420*self.scale),height))
        self.closed = False
        self.root.protocol('WM_DELETE_WINDOW',self._request_close)
        self.pending = PendingAction()
        self.notice = ''
        self.mode = None
        self._preview_split_initialized = False
        self.button_signature = None
        self.buttons=[]
        style=ttk.Style(self.root)
        if 'clam' in style.theme_names():style.theme_use('clam')
        self.root.configure(background='#eef3f9')
        style.configure('TFrame',background='#eef3f9')
        style.configure('TLabel',background='#eef3f9',foreground='#172b45')
        style.configure('TButton',padding=(12,7),background='#ffffff',foreground='#172b45',borderwidth=1)
        style.map('TButton',background=[('active','#e2ecfb')],foreground=[('disabled','#7e8da1')])
        style.configure('Accent.TButton',background='#2563b8',foreground='#ffffff')
        style.map('Accent.TButton',background=[('disabled','#e4eaf3'),('active','#1c4d94')],foreground=[('disabled','#7e8da1')])
        style.configure('TNotebook',background='#eef3f9',borderwidth=0)
        style.configure('TNotebook.Tab',padding=(12,6),background='#e2eaf4')
        style.map('TNotebook.Tab',background=[('selected','#ffffff')])
        style.configure('Title.TLabel',font=self.heading_font)
        style.configure('Treeview',rowheight=int(self.root.winfo_fpixels('1p')*22))
        self.root.columnconfigure(0,weight=1);self.root.rowconfigure(3,weight=1)
        self.header=ttk.Frame(self.root,padding=(16,10))
        self.header.grid(row=0,column=0,sticky='ew');self.header.columnconfigure(0,weight=1)
        self.title=ttk.Label(self.header,style='Title.TLabel');self.title.grid(row=0,column=0,sticky='w')
        self.summary=ttk.Label(self.header);self.summary.grid(row=1,column=0,sticky='w',pady=(4,0))
        self.toolbar=ttk.Frame(self.root,padding=(12,0));self.toolbar.grid(row=1,column=0,sticky='ew')
        self.toolbar.bind('<Configure>',self._wrap_buttons)
        self.info=ttk.Label(self.root,padding=(16,8),wraplength=900,justify='left')
        self.info.grid(row=2,column=0,sticky='ew')
        self.panes=ttk.Panedwindow(self.root,orient='vertical')
        self.panes.grid(row=3,column=0,sticky='nsew',padx=12)
        self.pair=ImagePair(self.panes,tk,ttk);self.panes.add(self.pair.frame,weight=3)
        self.tabs=ttk.Notebook(self.panes);self.panes.add(self.tabs,weight=2)
        table=ttk.Frame(self.tabs);table.rowconfigure(1,weight=1);table.columnconfigure(0,weight=1)
        self.frame_label=ttk.Label(table,padding=(8,6),wraplength=900)
        self.frame_label.grid(row=0,column=0,columnspan=2,sticky='ew')
        self.tree=ttk.Treeview(table,columns=('joint','x','y','z','state','reason'),show='headings',height=6)
        for name,label,w in [('joint','测量点',120),('x','X / mm',90),('y','Y / mm',90),('z','Z / mm',90),('state','状态',150),('reason','说明',220)]:
            self.tree.heading(name,text=label);self.tree.column(name,width=w,minwidth=60,stretch=True)
        self.tree.tag_configure('bad',foreground='#9a5e00');self.tree.tag_configure('ok',foreground='#12633b')
        self.tree.grid(row=1,column=0,sticky='nsew')
        vs=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);vs.grid(row=1,column=1,sticky='ns')
        hs=ttk.Scrollbar(table,orient='horizontal',command=self.tree.xview);hs.grid(row=2,column=0,sticky='ew')
        self.tree.configure(yscrollcommand=vs.set,xscrollcommand=hs.set)
        self.table_scrollbars=(vs,hs)
        self.calibration_help,calibration_help_text=scroll_text(table,tk,ttk)
        set_text(calibration_help_text,
            '① 完整棋盘格同时出现在左右画面，保持静止，等待自动采样。\n\n'
            '② 采样成功后，明显移动或倾斜棋盘格，再保持静止。\n\n'
            '③ 样本足够后点击「计算标定」。覆盖不同位置、距离和角度。\n\n'
            '手动采样保留强制采样能力；重复姿态会提示。返回测量不会替换已有标定。\n'
            '具体检测频率、角点运动及阻塞原因可在「详细诊断」中查看。')
        details,self.detail_text=scroll_text(self.tabs,tk,ttk)
        help_frame,self.help_text=scroll_text(self.tabs,tk,ttk);set_text(self.help_text,HELP)
        self.tabs.add(table,text='实时坐标');self.tabs.add(details,text='详细诊断');self.tabs.add(help_frame,text='使用帮助')
        self.bottom=ttk.Frame(self.root,padding=(16,8));self.bottom.grid(row=4,column=0,sticky='ew')
        self.bottom.columnconfigure(0,weight=1)
        self.status=ttk.Label(self.bottom,wraplength=900,justify='left');self.status.grid(row=0,column=0,sticky='ew')
        self.progress=ttk.Progressbar(self.bottom,maximum=100,length=140);self.progress.grid(row=0,column=1,padx=(8,0))
        self.menu=tk.Menu(self.root);self.advanced=tk.Menu(self.menu,tearoff=False)
        self.menu.add_cascade(label='高级工具',menu=self.advanced)
        self.menu.add_command(label='使用帮助',command=lambda:self.tabs.select(2))
        self.root.configure(menu=self.menu)
        self.root.bind('<Configure>',self._wrap_info)
        self.root.bind('<KeyPress>',self._keyboard)
        self.root.update_idletasks()
        # Initial sash placement is deferred until the first real frame: Tk can
        # replace an eager sash position during native window layout.

    def _initialize_preview_split(self):
        """Allocate visible height to the cameras after native layout settles.

        Run once only; subsequent splitter changes belong to the operator.
        Both the camera view and the data table remain resizable.
        """
        if self._preview_split_initialized:
            return
        pane_height = self.panes.winfo_height()
        if pane_height < 180:
            return
        try:
            self.panes.sashpos(0, int(pane_height * .52))
            self.root.update_idletasks()
            self._preview_split_initialized = True
        except self.tk.TclError:
            pass

    def _request_close(self):
        self.closed=True

    def _wrap_info(self,event=None):
        width=max(200,self.root.winfo_width()-40)
        self.info.configure(wraplength=width);self.status.configure(wraplength=max(150,width-160))
        self.frame_label.configure(wraplength=width)

    def _wrap_buttons(self,event=None):
        available=max(1,self.toolbar.winfo_width()-24)
        x=0;row=0;col=0
        for button in self.buttons:
            width=button.winfo_reqwidth()+8
            if x and x+width>available:row+=1;col=0;x=0
            button.grid(row=row,column=col,sticky='w',padx=4,pady=3)
            x+=width;col+=1

    def _keyboard(self,event):
        # Entry widgets are used by the modal world dialog; never steal typing.
        widget_class=event.widget.winfo_class()
        if widget_class in ('Entry','TEntry','TCombobox') or (widget_class=='Text' and str(event.widget['state'])!='disabled'):
            return
        if event.keysym=='Escape':key=27
        elif event.char and len(event.char)==1:key=ord(event.char.lower())
        else:return
        if key in map(ord,'clkw tfmgpdvsqrx'.replace(' ','')) or key in (27,ord(' ')):
            self.pending.offer(key,keyboard=True)
            return 'break'

    def _command(self,key):
        if key==ord('m'):
            self.tabs.select(1)
        if key==ord('x'):
            from tkinter import messagebox
            if not messagebox.askyesno('丢弃本次采样','确认丢弃当前采集会话的图片和样本？已有标定文件不受影响。',parent=self.root):return
        self.pending.offer(key)

    def _actions(self,view):
        actions=view['actions']
        signature=tuple((a.key,a.label,a.enabled) for a in actions)
        if signature!=self.button_signature:
            for button in self.buttons:button.destroy()
            self.buttons=[]
            for action in actions:
                button=self.ttk.Button(self.toolbar,text=action.label,
                    style='Accent.TButton' if action.key in (ord('w'),ord('r')) else 'TButton',
                    command=lambda k=action.key:self._command(k))
                button.configure(state='normal' if action.enabled else 'disabled');self.buttons.append(button)
            self.button_signature=signature;self._wrap_buttons()
        self.advanced.delete(0,'end')
        for action in view['extra_actions']:
            self.advanced.add_command(label=action.label,state='normal' if action.enabled else 'disabled',
                command=lambda k=action.key:self.pending.offer(k))

    def show(self,canvas=None,*,pair,view):
        if self.closed:return ord('q')
        self.pending.configure(view['mode'],view['actions']+view['extra_actions'])
        self._actions(view)
        if view['mode']!=self.mode:
            self.mode=view['mode'];self.tabs.select(0)
            calibration=self.mode=='calibration'
            self.tabs.tab(0,text='采样指导' if calibration else '实时坐标')
            if calibration:
                self.tree.grid_remove()
                for bar in self.table_scrollbars:bar.grid_remove()
                self.calibration_help.grid(row=1,column=0,sticky='nsew')
            else:
                self.calibration_help.grid_remove();self.tree.grid()
                for bar in self.table_scrollbars:bar.grid()
        self.title.configure(text=view['title']);self.summary.configure(text=view['summary'])
        self.info.configure(text=view['hint']);self.frame_label.configure(text=view['frame'])
        self.status.configure(text='\n'.join(x for x in [view['record_status'],self.notice,view.get('notice',''),view['warnings']] if x))
        if view['progress'] is None:self.progress.grid_remove()
        else:self.progress.grid();self.progress.configure(value=view['progress'])
        set_text(self.detail_text,view['details'])
        cells=view['rows']
        children=self.tree.get_children()
        while len(children)<len(cells):
            self.tree.insert('','end');children=self.tree.get_children()
        for item,values in zip(children,cells):self.tree.item(item,values=values,tags=('ok' if values[4]=='有效' else 'bad',))
        for item in children[len(cells):]:self.tree.delete(item)
        self.pair.render(pair)
        try:
            self.root.update()
            self._initialize_preview_split()
        except self.tk.TclError:self.closed=True
        return ord('q') if self.closed else self.pending.take()

    def save_calibration_file(self, current):
        """Choose a location for a byte-identical backup of the active NPZ."""
        from tkinter import filedialog
        p=Path(current)
        picked=filedialog.asksaveasfilename(
            parent=self.root,
            title='另存当前完整标定 NPZ（不会切换正在使用的文件）',
            initialdir=str(p.parent),
            initialfile=p.stem+'_backup.npz',
            defaultextension='.npz',
            filetypes=[('标定文件 NPZ','*.npz')],
        )
        return picked or None

    def confirm_npz_overwrite(self, path):
        from tkinter import messagebox
        return messagebox.askyesno(
            '确认覆盖已有 NPZ',
            f'目标文件已存在：\n{path}\n\n覆盖后旧文件内容将丢失。确定覆盖吗？',
            parent=self.root,
        )

    def choose_calibration_file(self, initialdir=None):
        """Choose an existing NPZ; file validation and activation live in runner."""
        from tkinter import filedialog
        picked = filedialog.askopenfilename(
            parent=self.root,
            title='选择上次保存的双目标定 NPZ 文件',
            initialdir=str(initialdir or Path.cwd()),
            filetypes=[('标定文件 NPZ', '*.npz'), ('所有文件', '*.*')],
        )
        return picked or None

    def confirm_calibration_file(self, path, warnings=()):
        from tkinter import messagebox
        notes='\n'.join(str(x) for x in warnings)
        message=(
            f'准备加载双目标定文件：\n{path}\n\n'
            '必须确认当前 LEFT/RIGHT 对应原来同一对物理摄像头，'
            '且它们的安装位置和方向未改变。\n'
            '编号相同不代表安装一定相同。'
        )
        if notes:
            message+=f'\n\n需要注意：\n{notes}'
        message+='\n\n确认切换为这份标定并立即应用吗？'
        return messagebox.askyesno('确认加载 NPZ 标定',message,parent=self.root)

    def notify(self,message):
        self.notice=str(message)

    def close(self):
        self.closed=True
        try:self.root.destroy()
        except self.tk.TclError:pass


def create_display(mode='auto'):
    if mode=='auto':mode=os.environ.get('STEREO_POSE_UI','auto').lower()
    if mode not in ('auto','tk','opencv'):
        raise ValueError('ui mode must be auto, tk or opencv')
    if mode != 'opencv' and desktop_available():
        enable_dpi_awareness()
        display=DesktopDisplay.__new__(DesktopDisplay)
        try:
            DesktopDisplay.__init__(display)
            print('[ui] 中文桌面界面已启用；窗口可缩放，操作按钮与原快捷键等价。')
            return display
        except Exception as error:
            if hasattr(display,'root'):
                display.close()
            # Toolkit initialization only. Processing failures are never hidden.
            print(f'[ui] desktop unavailable ({error}); using resizable OpenCV compatibility view')
    return HighGuiDisplay()
