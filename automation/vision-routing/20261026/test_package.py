"""Install the staged existing package twice into a temporary user directory."""
from pathlib import Path
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
STAGE = HERE / "package-stage"
BASH = r"C:\Program Files\Git\bin\bash.exe"
fixture = Path(tempfile.mkdtemp(prefix="claude-glm-dist-check-"))
profile = fixture / ".claude-glm"
profile.mkdir()
(profile / "settings.json").write_text(json.dumps({"model":"haiku", "env":{"CLAUDE_CODE_AUTO_COMPACT_WINDOW":"123456"},
    "permissions":{"defaultMode":"default"}, "custom_keep":"yes",
    "hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"echo PRESERVE_CUSTOM_HOOK"}]}]}}), encoding="utf-8")
(fixture / ".bashrc").write_text('claude-glm() {\n  echo legacy\n}\nkeep_me() { echo preserved; }\n', encoding="utf-8")
cmd = [shutil.which("pwsh"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(STAGE / "install-claude-glm.ps1"), "-SkipSmoke", "-UserDirectory", str(fixture)]
logs = []
hashes = []
backup_counts = []
for repeat in [1, 2]:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    logs.append({"repeat":repeat,"exit_code":proc.returncode,"stdout":proc.stdout,"stderr":proc.stderr})
    if proc.returncode:
        (HERE / "package-install-check.json").write_text(json.dumps({"fixture":str(fixture),"logs":logs},ensure_ascii=False,indent=2),encoding="utf-8")
        raise SystemExit(proc.stderr[-2500:] or proc.stdout[-2500:])
    files=[fixture/".bashrc",profile/"settings.json",profile/"local-hooks/prepare-bash-env.py",profile/"vision-routing/agents.json",profile/"vision-routing/routing.md"]
    hashes.append({str(p.relative_to(fixture)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    backup_counts.append(len(list(fixture.rglob("*.bak-claude-glm-*"))))
settings=json.loads((profile/"settings.json").read_text(encoding="utf-8"))
assert settings['model']=='glm-5.3'
assert settings['custom_keep']=='yes'
assert settings['env']['CLAUDE_CODE_AUTO_COMPACT_WINDOW']=='123456'
hooks=[h for g in settings['hooks']['SessionStart'] for h in g['hooks']]
assert sum('prepare-bash-env.py' in h.get('command','') for h in hooks)==1
assert any(h.get('command')=='echo PRESERVE_CUSTOM_HOOK' for h in hooks)
text=(fixture/'.bashrc').read_text(encoding='utf-8')
assert 'keep_me() { echo preserved; }' in text
assert len(re.findall(r'^claude-glm\(\)',text,re.M))==1
assert hashes[0]==hashes[1]
assert backup_counts[0]==backup_counts[1]
agents=json.loads((profile/'vision-routing/agents.json').read_text(encoding='utf-8'))
assert agents['vision-reader']['model']=='glm-5.3-flash' and agents['vision-reader']['tools']==['Read']

# Exercise installed function against these fixture payloads without replacing HOME.
# Only the config-root literal is adjusted in this separate, non-network probe copy.
probe_rc=fixture/'probe-only.bashrc'
text=text.replace('export CLAUDE_CONFIG_DIR=~/.claude-glm','export CLAUDE_CONFIG_DIR='+shlex.quote(str(profile).replace('\\','/')))
probe_rc.write_text(text,encoding='utf-8')
probe_script=str(HERE/'launcher_probe.py').replace('\\','/')
command='source '+shlex.quote(str(probe_rc).replace('\\','/'))+'; claude() { python '+shlex.quote(probe_script)+' "$@"; }; claude-glm <<< 1'
proc=subprocess.run([BASH,'--noprofile','--norc','-c',command],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20)
probe=next(json.loads(line) for line in proc.stdout.splitlines() if line.startswith('{"probe":'))
assert probe['main_model_options']==['glm-5.3'] and probe['agents']['vision-reader']['model']=='glm-5.3-flash'
result={'status':'PASS','fixture':str(fixture),'real_api_requests':0,'legacy_haiku_migrated':True,'custom_settings_and_hooks_preserved':True,
        'single_launcher':True,'second_install_identical':hashes[0]==hashes[1],'second_install_no_new_backups':backup_counts[0]==backup_counts[1],
        'backup_counts':backup_counts,'installed_visual_agent':agents['vision-reader']['model'],'portable_launcher_probe':probe,'logs':logs,'installed_hashes':hashes[-1]}
(HERE/'package-install-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['logs','installed_hashes']},ensure_ascii=False))
