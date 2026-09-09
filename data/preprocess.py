"""
Preprocesses the NSL-KDD dataset into a clean format the Triage Agent can use.

NSL-KDD has 41 features per network connection record + a label (attack type or 'normal').
We map the ~40 specific attack labels into 5 broad categories, which is the standard
approach used in NSL-KDD research papers:

    normal  -> Normal traffic
    dos     -> Denial of Service (e.g. neptune, smurf, back)
    probe   -> Scanning/reconnaissance (e.g. portsweep, nmap, satan)
    r2l     -> Remote-to-Local: unauthorized access from a remote machine (e.g. guess_passwd, ftp_write)
    u2r     -> User-to-Root: privilege escalation (e.g. buffer_overflow, rootkit)

This mirrors what a real SOC alert would look like: "here's a connection, what kind of
threat (if any) is this?"
"""
import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

COLUMNS = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes",
    "land", "wrong_fragment", "urgent", "hot", "num_failed_logins", "logged_in",
    "num_compromised", "root_shell", "su_attempted", "num_root", "num_file_creations",
    "num_shells", "num_access_files", "num_outbound_cmds", "is_host_login",
    "is_guest_login", "count", "srv_count", "serror_rate", "srv_serror_rate",
    "rerror_rate", "srv_rerror_rate", "same_srv_rate", "diff_srv_rate",
    "srv_diff_host_rate", "dst_host_count", "dst_host_srv_count",
    "dst_host_same_srv_rate", "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate", "dst_host_srv_serror_rate",
    "dst_host_rerror_rate", "dst_host_srv_rerror_rate", "label", "difficulty"
]

ATTACK_MAP = {
    "normal": "normal",
    # DoS
    "back": "dos", "land": "dos", "neptune": "dos", "pod": "dos", "smurf": "dos",
    "teardrop": "dos", "apache2": "dos", "udpstorm": "dos", "processtable": "dos",
    "worm": "dos", "mailbomb": "dos",
    # Probe
    "satan": "probe", "ipsweep": "probe", "nmap": "probe", "portsweep": "probe",
    "mscan": "probe", "saint": "probe",
    # R2L
    "guess_passwd": "r2l", "ftp_write": "r2l", "imap": "r2l", "phf": "r2l",
    "multihop": "r2l", "warezmaster": "r2l", "warezclient": "r2l", "spy": "r2l",
    "xlock": "r2l", "xsnoop": "r2l", "snmpguess": "r2l", "snmpgetattack": "r2l",
    "httptunnel": "r2l", "sendmail": "r2l", "named": "r2l",
    # U2R
    "buffer_overflow": "u2r", "loadmodule": "u2r", "rootkit": "u2r", "perl": "u2r",
    "sqlattack": "u2r", "xterm": "u2r", "ps": "u2r",
}

def load_and_clean(path):
    df = pd.read_csv(path, names=COLUMNS)
    df = df.drop(columns=["difficulty"])
    df["category"] = df["label"].map(lambda x: ATTACK_MAP.get(x, "unknown"))
    unknown = df[df["category"] == "unknown"]["label"].unique()
    if len(unknown) > 0:
        print(f"Warning: {len(unknown)} unmapped labels found (dropping): {list(unknown)}")
        df = df[df["category"] != "unknown"]
    return df


def ensure_clean_data():
    """Generates train_clean.csv/test_clean.csv if missing. Used by
    TriageAgent.load() to self-heal on fresh deployments (Streamlit Cloud etc.)."""
    train_path = os.path.join(SCRIPT_DIR, "train_clean.csv")
    test_path = os.path.join(SCRIPT_DIR, "test_clean.csv")
    if os.path.exists(train_path) and os.path.exists(test_path):
        return
    train = load_and_clean(os.path.join(SCRIPT_DIR, "KDDTrain.txt"))
    test = load_and_clean(os.path.join(SCRIPT_DIR, "KDDTest.txt"))
    train.to_csv(train_path, index=False)
    test.to_csv(test_path, index=False)


if __name__ == "__main__":
    train = load_and_clean(os.path.join(SCRIPT_DIR, "KDDTrain.txt"))
    test = load_and_clean(os.path.join(SCRIPT_DIR, "KDDTest.txt"))
    train.to_csv(os.path.join(SCRIPT_DIR, "train_clean.csv"), index=False)
    test.to_csv(os.path.join(SCRIPT_DIR, "test_clean.csv"), index=False)
    print("\nTrain category distribution:")
    print(train["category"].value_counts())
    print("\nTest category distribution:")
    print(test["category"].value_counts())
