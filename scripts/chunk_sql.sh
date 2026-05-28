#!/usr/bin/env bash
# SQL-based batch chunking via docker exec
set -e
CATEGORIES="${CHUNK_CATEGORIES:-}"
DB_CMD="docker exec -i zhineng-postgres psql -U zhineng -d zhineng_kb -t -A"

echo "$(date '+%H:%M:%S') Starting SQL chunking for categories: ${CATEGORIES:-ALL}"

if [ -n "$CATEGORIES" ]; then
    CAT_LIST=$(echo "$CATEGORIES" | sed "s/,/','/g")
    CAT_WHERE="AND d.category IN ('$CAT_LIST')"
else
    CAT_WHERE=""
fi

UNCHUNKED=$($DB_CMD -c "
SELECT COUNT(*) FROM documents d
WHERE length(d.content) > 400 $CAT_WHERE
  AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id);")
echo "$(date '+%H:%M:%S') Unchunked docs: $UNCHUNKED"

if [ "$UNCHUNKED" = "0" ] || [ -z "$UNCHUNKED" ]; then
    echo "Nothing to do."
    exit 0
fi

DOC_IDS=$($DB_CMD -c "
SELECT id FROM documents d
WHERE length(d.content) > 400 $CAT_WHERE
  AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id)
ORDER BY id;")

COUNT=0
TOTAL_CHUNKS=0
START=$(date +%s)

for DOC_ID in $DOC_IDS; do
    [ -z "$DOC_ID" ] && continue

    CHUNKS=$($DB_CMD -c "
    WITH doc AS (SELECT id, content FROM documents WHERE id = $DOC_ID),
    chunks AS (
      SELECT doc.id as doc_id, gs.n as chunk_index,
        substring(doc.content from (gs.n * 300 - 299) for 300) as content
      FROM doc, generate_series(1, ceil(length(doc.content) / 300.0)::int) as gs(n)
    )
    INSERT INTO doc_chunks (doc_id, chunk_index, content)
    SELECT doc_id, chunk_index, content FROM chunks
    ON CONFLICT (doc_id, chunk_index) DO NOTHING;" 2>&1 | grep -oP 'INSERT 0 \K\d+' || echo 0)

    COUNT=$((COUNT + 1))
    TOTAL_CHUNKS=$((TOTAL_CHUNKS + ${CHUNKS:-0}))

    if [ $((COUNT % 5)) -eq 0 ]; then
        ELAPSED=$(($(date +%s) - START))
        echo "$(date '+%H:%M:%S') Progress: $COUNT/$UNCHUNKED docs, $TOTAL_CHUNKS chunks, ${ELAPSED}s"
    fi
done

ELAPSED=$(($(date +%s) - START))
echo "$(date '+%H:%M:%S') Done: $COUNT docs, $TOTAL_CHUNKS chunks in ${ELAPSED}s"
