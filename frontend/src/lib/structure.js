// Rebuild the editor's local rows after the server's structure changes,
// without throwing away edits the admin hasn't saved yet.
//
// A local row is kept when the server didn't change that row (so the edit is
// still against what's on the server). Rows the server did change, and any
// add/remove (length change), take the server's version.
export function mergeRows(localRows, oldServer, newServer) {
  const sameShape = localRows.length === newServer.length
    && oldServer.length === newServer.length;
  return newServer.map((entry, i) => {
    const unchangedOnServer = sameShape
      && JSON.stringify(oldServer[i]) === JSON.stringify(entry);
    return unchangedOnServer ? localRows[i] : { ...entry };
  });
}
