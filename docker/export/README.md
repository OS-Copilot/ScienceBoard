# Reference image export

This directory is for maintainers creating the parity image.  It is **not** a
cloud runtime dependency.  A cloud machine consumes the resulting Docker image
and never invokes VMware.

From a machine that has the official reference VM and its `sci_bench`
snapshot:

```bash
python docker/export/export_reference.py \
  /path/to/Ubuntu.vmx \
  --output .artifacts/scienceboard-rootfs.tar.gz

docker/import_rootfs.sh .artifacts/scienceboard-rootfs.tar.gz
```

The importer first applies the runtime/sanitizing overlay and then flattens
the resulting filesystem. Only the final `scienceboard:0.1` image should be
distributed; the local `scienceboard-rootfs:0.1` and
`scienceboard-layered:0.1` build inputs can contain data in historical layers.
The exporter also excludes SSH identity material, shell histories, persistent
machine identity, random seeds, and NetworkManager connection secrets.

The export deliberately uses `/home/user`, not `/tmp`, because the reference
guest clears `/tmp` during a clean shutdown.  It also omits `/proc`, `/sys`,
`/dev`, `/run`, VM logs, and sockets.  Docker recreates those pseudo
filesystems.  The script accepts GNU tar's “file changed” status only after a
full gzip test and an explicit check for the custom applications, Lean
project, and GRASS datasets.

Do not publish the resulting image until ChimeraX redistribution terms have
been reviewed.  A local image or private registry is the expected default.
