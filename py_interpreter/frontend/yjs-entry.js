// Pinned, self-hosted browser runtime. Build with `npm ci && npm run build`.
export {
    Doc, UndoManager, applyUpdate, mergeUpdates, encodeStateAsUpdate, encodeStateVector,
    createRelativePositionFromTypeIndex, createAbsolutePositionFromRelativePosition,
    encodeRelativePosition, decodeRelativePosition,
} from 'yjs';
