// src/lib/volumes.js

// Distinct volume numbers in a chapter list, in order of first
// appearance. Pass the output of getPublishedChaptersSorted().
export function getVolumes(chapters) {
  return [...new Set(chapters.map((chapter) => chapter.data.volume))];
}
