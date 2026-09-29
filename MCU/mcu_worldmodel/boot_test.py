"""Minimal boot test: can MinecraftSim start, reset, step, and report the info keys
this system depends on?"""
import getpass
import os, sys, time
os.environ.setdefault("MINESTUDIO_DIR", f"/n/netscratch/sham_lab/Lab/{getpass.getuser()}/MineStudio")
sys.path.insert(0, ".")
t0 = time.time()
from minestudio.simulator import MinecraftSim
print(f"[{time.time()-t0:.0f}s] imported", flush=True)
sim = MinecraftSim(action_type="env", obs_size=(128,128), render_size=(640,360), callbacks=[])
print(f"[{time.time()-t0:.0f}s] constructed", flush=True)
obs, info = sim.reset()
print(f"[{time.time()-t0:.0f}s] reset OK", flush=True)
print("obs keys:", list(obs.keys()))
print("info keys:", sorted(info.keys()))
for k in ("inventory","location_stats","mine_block","craft_item","kill_entity","pov","isGuiOpen"):
    v = info.get(k)
    print(f"  {k}: {type(v).__name__}", (list(v)[:4] if isinstance(v,dict) else getattr(v,'shape',v)))
a = sim.noop_action(); a["forward"]=1
for i in range(5):
    obs, r, term, trunc, info = sim.step(a)
print(f"[{time.time()-t0:.0f}s] stepped 5x OK; loc={info.get('location_stats')}", flush=True)
sim.close()
print(f"[{time.time()-t0:.0f}s] DONE", flush=True)
