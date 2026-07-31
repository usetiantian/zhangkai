import sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit.chain import AuditChain
path=Path(sys.argv[1]);prefix=sys.argv[2];count=int(sys.argv[3])
chain=AuditChain(path,lock_timeout_seconds=10,lock_poll_seconds=.01)
for index in range(count):
 chain.append(f"{prefix}-{index}",datetime.now(timezone.utc),"concurrent",None,"ok",{})
