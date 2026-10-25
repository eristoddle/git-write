// Reference reader for the annotation format in docs/ANNOTATION_FORMAT.md, in plain JS on
// isomorphic-git. It is what the Veneer plugin has to do, so it doubles as an executable spec.
import git from 'isomorphic-git';
import YAML from 'yaml';
import fs from 'node:fs';

export const REQUIRED = ['file_path', 'highlighted_text', 'start_line', 'end_line', 'comment', 'author'];
export const STATUSES = ['new', 'accepted', 'rejected'];

// Annotation body of a commit message (subject, blank line, YAML mapping), or null.
export function parseAnnotationMessage(message) {
  const parts = message.split('\n');
  if (parts.length < 3 || parts[1].trim() !== '') return null;
  let data;
  try {
    data = YAML.parse(parts.slice(2).join('\n'));
  } catch {
    return null;
  }
  if (data === null || typeof data !== 'object' || Array.isArray(data)) return null;
  if (!REQUIRED.every((field) => field in data)) return null;
  if (!STATUSES.includes(data.status)) return null;
  if (!Number.isInteger(data.start_line) || !Number.isInteger(data.end_line)) return null;
  return data;
}

const optionalString = (v) => (typeof v === 'string' ? v : null);
const optionalInt = (v) => (Number.isInteger(v) && v >= 0 ? v : null);

// All annotations on `branch`, each at its latest status, oldest thread first.
export async function listAnnotations(dir, branch) {
  let commits;
  try {
    commits = await git.log({ fs, dir, ref: branch });
  } catch {
    return [];
  }
  const threads = new Map();
  for (const { oid, commit } of [...commits].reverse()) {
    const data = parseAnnotationMessage(commit.message);
    if (!data) continue;
    const id = data.original_annotation_id || oid;
    threads.set(id, {
      id,
      commit_id: oid,
      file_path: data.file_path,
      highlighted_text: data.highlighted_text,
      start_line: data.start_line,
      end_line: data.end_line,
      comment: data.comment,
      author: data.author,
      status: data.status,
      prefix: optionalString(data.prefix),
      suffix: optionalString(data.suffix),
      offset: optionalInt(data.offset),
      original_annotation_id: data.original_annotation_id || null,
    });
  }
  return [...threads.values()];
}

// Code-point aware anchor, as the format specifies (offset and context count code points).
export function computeAnchor(text, highlighted) {
  const chars = Array.from(text);
  const needle = Array.from(highlighted);
  for (let i = 0; i + needle.length <= chars.length; i++) {
    if (needle.every((c, k) => chars[i + k] === c)) {
      return {
        prefix: chars.slice(Math.max(0, i - 32), i).join(''),
        suffix: chars.slice(i + needle.length, i + needle.length + 32).join(''),
        offset: i,
      };
    }
  }
  return null;
}
