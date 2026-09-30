JOINT_NAMES = [
    "nose",
    "left_eye", "right_eye",
    "left_ear", "right_ear",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
]

JOINT_INDEX = {name: i for i, name in enumerate(JOINT_NAMES)}

JOINT_GROUPS = {
    "all": JOINT_NAMES,
    "ergonomics": [
        "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow",
        "left_wrist", "right_wrist",
        "left_hip", "right_hip",
        "left_knee", "right_knee",
        "left_ankle", "right_ankle",
    ],
    "upper": [
        "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow",
        "left_wrist", "right_wrist",
    ],
    "lower": [
        "left_hip", "right_hip",
        "left_knee", "right_knee",
        "left_ankle", "right_ankle",
    ],
    "core": [
        "left_shoulder", "right_shoulder",
        "left_hip", "right_hip",
    ],
}

def resolve_joints(group="ergonomics", explicit=None):
    if explicit:
        unknown = [x for x in explicit if x not in JOINT_INDEX]
        if unknown:
            raise ValueError(f"Unknown joints: {unknown}")
        return explicit
    if group not in JOINT_GROUPS:
        raise ValueError(f"Unknown joint group: {group}. Available: {list(JOINT_GROUPS)}")
    return JOINT_GROUPS[group]
