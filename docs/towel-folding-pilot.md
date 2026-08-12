# Towel-folding Gate A/B pilot

Status: local heuristic pilot, 2026-08-11. No model call was made and this is
not a Gate A or Gate B pass.

## Supplied evidence

Three files were supplied under the ignored `experiments/vids/` directory.
`demo-a-teacher.mkv` and `demo-a-student.mkv` have the same byte length and the
same SHA-256 hash. They are therefore one recording with two filenames, not
independent teacher and learner evidence. `demo-b.mkv` is independent.

The two unique sources are 1080p/60fps at approximately 112–116 Mbps. The local
low-bandwidth path decoded them into 640-pixel, 8-fps proxies and sampled twelve
512-pixel JPEG frames:

- demo A: 225,043,369 source bytes → 198,372 proxy bytes and 82,891 sampled
  frame bytes;
- demo B: 354,958,564 source bytes → 270,180 proxy bytes and 80,689 sampled
  frame bytes.

Raw video and proxy video are not model inputs. A model request can contain only
the sampled JPEGs and optional mono 16 kHz audio, and the application now rejects
a combined model-media payload above 5 MiB.

## Heuristic visual result

Both unique recordings start with a flat pink towel and include an early
horizontal fold. They then diverge. Demo A finishes as a narrow rectangular
roll/fold; demo B adds diagonal folds and finishes as a triangular shape. The
end states are visibly different and the later processes are not the same.

For Gate A, this exposes a useful candidate blocker: “fold a towel” does not
specify the intended final shape. The targeted teacher question is whether the
learner should produce demo A's narrow rectangle or demo B's triangle.

For a Gate B pilot, demo A can be the reference and demo B can be an alternative
end state. The duplicate student file is useful only as an exact-match pipeline
sanity check. It cannot serve as independent held-out evidence.

The detailed ignored report and low-resolution review assets are under
`runs/towel-jugaad/`.
