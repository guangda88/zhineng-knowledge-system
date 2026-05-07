#!/bin/bash
# Auto-complete remaining DB rebuild tasks after tsv_content finishes
# Run in background: nohup bash scripts/finish_rebuild.sh > /tmp/rebuild.log 2>&1 &

set -e
PSQL="docker exec zhineng-postgres psql -U zhineng -d zhineng_kb -t"

echo "[$(date)] Waiting for tsv_content column to appear..."
for i in $(seq 1 120); do
    RESULT=$($PSQL -c "SELECT attname FROM pg_attribute WHERE attrelid = 'documents'::regclass AND attname = 'tsv_content';" 2>/dev/null | tr -d ' ')
    if [ "$RESULT" = "tsv_content" ]; then
        echo "[$(date)] tsv_content column created successfully!"
        break
    fi
    if [ $i -eq 120 ]; then
        echo "[$(date)] TIMEOUT: tsv_content not found after 60 minutes. Attempting ALTER TABLE..."
        docker exec zhineng-postgres psql -U zhineng -d zhineng_kb -c \
            "ALTER TABLE documents ADD COLUMN tsv_content tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, (COALESCE(title, ''::character varying)::text || ' '::text) || COALESCE(content, ''::text))) STORED;"
        echo "[$(date)] ALTER TABLE completed."
    fi
    sleep 30
done

echo "[$(date)] Verifying indexes..."
$PSQL -c "SELECT indexname FROM pg_indexes WHERE tablename='documents' AND indexname LIKE 'idx_documents_%' ORDER BY indexname;"

echo "[$(date)] Document counts:"
$PSQL -c "SELECT category, COUNT(*) FROM documents GROUP BY category ORDER BY COUNT(*) DESC;"

echo "[$(date)] Total count:"
$PSQL -c "SELECT COUNT(*) FROM documents;"

echo "[$(date)] Restarting API container..."
docker start zhineng-api

echo "[$(date)] Waiting for API to be healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        echo "[$(date)] API is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "[$(date)] WARNING: API not healthy after 5 minutes"
    fi
    sleep 10
done

echo "[$(date)] All done! Rebuild complete."
echo "[$(date)] Final counts:"
$PSQL -c "SELECT category, COUNT(*) FROM documents GROUP BY category ORDER BY COUNT(*) DESC;"
