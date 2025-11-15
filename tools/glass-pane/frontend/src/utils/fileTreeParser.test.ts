import { describe, it, expect } from 'vitest';
import { parseFileTree } from './fileTreeParser';

describe('File Tree Parser', () => {
  it('should parse flat file list into tree', () => {
    const files = ['src/App.tsx', 'src/main.tsx', 'README.md'];
    const tree = parseFileTree(files);

    expect(tree).toHaveLength(2); // 'src' dir and 'README.md'
    expect(tree[0].type).toBe('directory');
    expect(tree[0].name).toBe('src');
    expect(tree[0].children).toHaveLength(2);
  });

  it('should handle nested directories', () => {
    const files = ['src/components/App.tsx', 'src/utils/helpers.ts'];
    const tree = parseFileTree(files);

    const srcDir = tree.find(n => n.name === 'src');
    expect(srcDir?.children).toHaveLength(2); // 'components' and 'utils'
  });

  it('should sort files alphabetically', () => {
    const files = ['zebra.txt', 'apple.txt', 'banana.txt'];
    const tree = parseFileTree(files);

    expect(tree[0].name).toBe('apple.txt');
    expect(tree[1].name).toBe('banana.txt');
    expect(tree[2].name).toBe('zebra.txt');
  });
});
