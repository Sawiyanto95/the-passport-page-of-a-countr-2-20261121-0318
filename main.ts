// The Passport Page of a Country That Isn't There.
// Entry program: writes the invented passport spread to /output/entry.png.
//
// The spread is rendered by render.py (Pillow) into entry.png, committed
// in this repository. This program copies that file into the output
// directory. The copy is deterministic: the same file, byte for byte,
// on every run.
//
// The output directory is a mounted volume in the grader: never remove
// the directory itself, only its contents.
import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const outDir = "/output";

mkdirSync(outDir, { recursive: true });
for (const child of readdirSync(outDir)) {
  rmSync(join(outDir, child), { recursive: true, force: true });
}

const src = join(here, "entry.png");
if (!existsSync(src)) {
  throw new Error("entry.png is missing from the repository");
}
copyFileSync(src, join(outDir, "entry.png"));
console.log("wrote /output/entry.png");
