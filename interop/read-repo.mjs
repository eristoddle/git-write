// Usage: node read-repo.mjs <repo-dir> [feedback-branch]
// Reads a GitWrite repository with isomorphic-git and prints what it sees as JSON.
import git from 'isomorphic-git';
import fs from 'node:fs';
import { listAnnotations } from './lib.mjs';

const [dir, feedback = 'feedback'] = process.argv.slice(2);
if (!dir) {
  console.error('usage: node read-repo.mjs <repo-dir> [feedback-branch]');
  process.exit(2);
}

const branches = (await git.listBranches({ fs, dir })).sort();
const current = await git.currentBranch({ fs, dir, fullname: false });

const history = (await git.log({ fs, dir, ref: current })).map(({ oid, commit }) => ({
  oid,
  subject: commit.message.split('\n')[0],
  author: commit.author.name,
}));

const tags = [];
for (const name of (await git.listTags({ fs, dir })).sort()) {
  const oid = await git.resolveRef({ fs, dir, ref: `refs/tags/${name}` });
  const { type, object } = await git.readObject({ fs, dir, oid });
  if (type === 'tag') {
    tags.push({ name, type: 'annotated', target: object.object, message: object.message.trim() });
  } else {
    tags.push({ name, type: 'lightweight', target: oid });
  }
}

// Feedback commits change no files: their tree must equal their parent's tree.
const feedbackCommits = [];
if (branches.includes(feedback)) {
  for (const { oid, commit } of await git.log({ fs, dir, ref: feedback })) {
    const parent = commit.parent[0];
    const parentTree = parent ? (await git.readCommit({ fs, dir, oid: parent })).commit.tree : null;
    feedbackCommits.push({ oid, subject: commit.message.split('\n')[0], sameTreeAsParent: parentTree === commit.tree });
  }
}

console.log(JSON.stringify({
  branches,
  current,
  history,
  tags,
  feedbackCommits,
  annotations: await listAnnotations(dir, feedback),
}));
