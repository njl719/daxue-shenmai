# -*- coding: utf-8 -*-
"""备份恢复工具:把 backups/backup-<stamp>-<tag> 恢复为当前 data/。

用法:
    python tools/restore_backup.py             # 列出可用备份(只读)
    python tools/restore_backup.py --apply <备份目录名>
      → 需要交互键入 RESTORE 确认;恢复前自动对当前数据做一次 pre-restore 安全备份。

安全设计:默认 dry-run;不做任何"先删后建";镜像式恢复(删除备份里没有的多余文件);
恢复前强制安全备份;服务运行时建议先停止(文件级拷贝不锁库,单用户 JSON 风险低但求稳)。
"""
import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.storage import Store  # noqa: E402

CONFIRM_WORD = "RESTORE"


def list_backups(backup_dir):
    if not os.path.isdir(backup_dir):
        return []
    out = []
    for name in sorted(os.listdir(backup_dir), reverse=True):
        path = os.path.join(backup_dir, name)
        if name.startswith("backup-") and os.path.isdir(path):
            n = sum(1 for f in os.listdir(path) if f.endswith(".json"))
            out.append((name, path, n))
    return out


def mirror_copy(src_dir, dst_dir):
    """把 src 镜像到 dst:拷贝/覆盖同路径文件,删除 dst 中 src 没有的文件。"""
    copied = removed = 0
    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target = os.path.normpath(os.path.join(dst_dir, rel))
        os.makedirs(target, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(target, f))
            copied += 1
    for root, _dirs, files in os.walk(dst_dir):
        rel = os.path.relpath(root, dst_dir)
        src_root = os.path.normpath(os.path.join(src_dir, rel))
        for f in files:
            if not os.path.exists(os.path.join(src_root, f)):
                os.remove(os.path.join(root, f))
                removed += 1
    return copied, removed


def restore(backup_dir, data_dir, backup_name, apply=False, backup_dir_root=None):
    """核心逻辑(可单测)。apply=False 只做预检并返回计划。"""
    src = os.path.join(backup_dir, backup_name)
    if not backup_name.startswith("backup-") or not os.path.isdir(src):
        return {"ok": False, "error": "备份不存在或名称不合法:%s" % backup_name}
    n_files = sum(1 for _r, _d, fs in os.walk(src) for _f in fs)
    plan = {"ok": True, "backup": backup_name, "files": n_files,
            "safety_backup": None, "copied": 0, "removed": 0}
    if not apply:
        return plan
    if backup_dir_root is None:
        backup_dir_root = backup_dir
    store = Store(data_dir=data_dir, backup_dir=backup_dir_root)
    plan["safety_backup"] = store.backup("pre-restore")
    copied, removed = mirror_copy(src, data_dir)
    plan["copied"], plan["removed"] = copied, removed
    return plan


def main():
    ap = argparse.ArgumentParser(description="大雪深埋 备份恢复工具")
    ap.add_argument("--apply", metavar="备份目录名", help="执行恢复(默认只列出备份)")
    args = ap.parse_args()

    store = Store()
    backups = list_backups(store.backup_dir)
    if not backups:
        print("backups/ 下没有可用备份。")
        sys.exit(1)
    print("可用备份(新→旧):")
    for name, _p, n in backups:
        print("  %s  (%d 个 json 文件)" % (name, n))

    if not args.apply:
        print("\n这是只读预览。执行恢复:python tools/restore_backup.py --apply <备份目录名>")
        print("恢复前会自动做一次 pre-restore 安全备份;建议先停止本地服务。")
        return

    if args.apply not in {b[0] for b in backups}:
        print("[错误] 备份不存在:%s" % args.apply)
        sys.exit(1)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ans = input("将把当前 data/ 恢复为 %s。键入 %s 确认(其他输入取消):"
                % (args.apply, CONFIRM_WORD))
    if ans.strip() != CONFIRM_WORD:
        print("已取消,未做任何修改。")
        return
    plan = restore(store.backup_dir, store.data_dir, args.apply,
                   apply=True, backup_dir_root=store.backup_dir)
    print("安全备份(恢复前):", plan["safety_backup"])
    print("已拷贝 %d 个文件,移除 %d 个多余文件。" % (plan["copied"], plan["removed"]))
    print("完成。重新启动服务后生效:python run.py")


if __name__ == "__main__":
    main()
