// Usage: node write-repo.mjs <new-repo-dir>
// Builds a GitWrite-shaped project with isomorphic-git only: commits, an exploration branch, tags,
// and a feedback branch holding an annotation and a status change. Prints the ids as JSON.
import git from 'isomorphic-git';
import YAML from 'yaml';
import fs from 'node:fs';
import path from 'node:path';
import { computeAnchor } from './lib.mjs';

const [dir] = process.argv.slice(2);
if (!dir) {
  console.error('usage: node write-repo.mjs <new-repo-dir>');
  process.exit(2);
}

const author = { name: 'Iso Writer', email: 'iso@example.com' };
const write = (name, text) => fs.writeFileSync(path.join(dir, name), text);

fs.mkdirSync(dir, { recursive: true });
await git.init({ fs, dir, defaultBranch: 'main' });

const CHAPTER = 'The rain had not stopped for three days.\nMarta counted the sandbags twice. 😀 Then she counted them again.\nBy evening the road was gone.\n';
write('chapter1.md', CHAPTER);
await git.add({ fs, dir, filepath: 'chapter1.md' });
const first = await git.commit({ fs, dir, message: 'Chapter 1 draft', author });

await git.branch({ fs, dir, ref: 'alt-ending', checkout: true });
write('ending.md', 'She left at dawn.\n');
await git.add({ fs, dir, filepath: 'ending.md' });
const altTip = await git.commit({ fs, dir, message: 'Alternate ending', author });

await git.checkout({ fs, dir, ref: 'main' });
write('chapter1.md', CHAPTER + 'The end, for now.\n');
await git.add({ fs, dir, filepath: 'chapter1.md' });
const second = await git.commit({ fs, dir, message: 'Main revision', author });

await git.tag({ fs, dir, ref: 'draft-1', object: first });
await git.annotatedTag({ fs, dir, ref: 'v1', object: second, message: 'First complete draft', tagger: author });

// Feedback branch: same tree as the commit it starts from, YAML body, never checked out.
const highlighted = 'Marta counted the sandbags twice. 😀';
const anchor = computeAnchor(CHAPTER, highlighted);
const feedbackCommit = async (parent, subject, body) => {
  const { commit } = await git.readCommit({ fs, dir, oid: parent });
  return git.writeCommit({
    fs, dir,
    commit: {
      message: `${subject}\n\n${YAML.stringify(body)}`,
      tree: commit.tree,
      parent: [parent],
      author: { ...author, timestamp: Math.floor(Date.now() / 1000), timezoneOffset: 0 },
      committer: { ...author, timestamp: Math.floor(Date.now() / 1000), timezoneOffset: 0 },
    },
  });
};
const annotation = {
  file_path: 'chapter1.md',
  highlighted_text: highlighted,
  start_line: 1,
  end_line: 1,
  comment: 'Show her fear: "tell" less, and mind the colon: here.',
  author: 'reader@example.com',
  status: 'new',
  ...anchor,
};
const annotationId = await feedbackCommit(second, 'Annotation: chapter1.md (Lines 1-1)', annotation);
await git.writeRef({ fs, dir, ref: 'refs/heads/feedback', value: annotationId });
const statusId = await feedbackCommit(annotationId, `Update status: chapter1.md (Annotation ${annotationId.slice(0, 7)}) to accepted`, {
  ...annotation,
  status: 'accepted',
  original_annotation_id: annotationId,
});
await git.writeRef({ fs, dir, ref: 'refs/heads/feedback', value: statusId, force: true });

console.log(JSON.stringify({
  first, second, altTip, annotationId, statusId,
  highlighted, anchor, comment: annotation.comment,
}));
