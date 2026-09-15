# Delivering the reference image

The source pull request deliberately excludes the reference VM filesystem and
all generated Docker images. The final flattened image is large and includes
third-party desktop applications, so it should be shared with maintainers as a
private compressed artifact during review.

Only publish the final sanitized image. Never upload the exported rootfs or the
intermediate `scienceboard-rootfs:*` and `scienceboard-layered:*` images because
they can retain VM state in historical layers.

## Reviewer artifact

Run the packaging script. It audits the image before saving it and records the
archive checksum:

```bash
scripts/package_distribution.sh scienceboard:0.1
```

Upload the `.tar.zst` to a private Hugging Face repository or object-storage
bucket, grant the ScienceBoard maintainers read access, and put its checksum in
the pull request. Keep the artifact private while the pull request is under
review. A maintainer can then verify and load it:

```bash
sha256sum -c scienceboard-docker-0.1.tar.zst.sha256
zstd -dc scienceboard-docker-0.1.tar.zst | docker load
python3 scripts/audit_distribution.py --image scienceboard:0.1
```

[GitHub Container Registry is not suitable](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#troubleshooting)
for the current archive: it limits each layer to 10 GB, while flattening
intentionally creates one sanitized layer whose compressed content is larger
than that limit. Git repositories, Git LFS, and GitHub release assets are also
poor fits for this multi-gigabyte artifact. Hugging Face supports resumable
large-file uploads and is already used for the official ScienceBoard VM.

## Public release

Public distribution needs a separate license review. In particular,
[UCSF ChimeraX](https://www.cgl.ucsf.edu/chimerax/docs/licensing.html) requires
users to accept its license before downloading it and has separate commercial
licensing terms. Confirm redistribution permission with the ScienceBoard
maintainers and the relevant application licensors before making the package
or an archive publicly accessible.

After that review, the preferred public home is the existing
[`OS-Copilot/ScienceBoard-Env`](https://huggingface.co/OS-Copilot/ScienceBoard-Env)
Hugging Face repository alongside the official VM, with the checksum and load
command documented. The maintainers can instead publish an image rebuilt from
an authorized reference VM. The source pull request remains useful without
embedding a multi-gigabyte binary artifact.
