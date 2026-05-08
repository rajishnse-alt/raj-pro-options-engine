#!/bin/bash
# Quick command to view latest logs

cd "$(dirname "$0")"

echo "📋 Latest Captured Logs"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Find latest log file
LATEST=$(ls -t logs/upstox_data_dump_*.log 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
    echo "❌ No logs found. Run the Streamlit app first:"
    echo "   streamlit run app.py"
    exit 1
fi

echo "📁 File: $LATEST"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""

# Show CRITICAL section
if grep -q "\[CRITICAL\]" "$LATEST"; then
    echo "🔍 [CRITICAL] UPSTOX DATA STRUCTURE:"
    echo "───────────────────────────────────────────────────────"
    grep -A 50 "\[CRITICAL\]" "$LATEST" | head -60
    echo ""
fi

# Show DATA-DUMP section
if grep -q "\[DATA-DUMP\]" "$LATEST"; then
    echo "📤 [DATA-DUMP] FROM APP:"
    echo "───────────────────────────────────────────────────────"
    grep -A 30 "\[DATA-DUMP\]" "$LATEST" | head -40
    echo ""
fi

echo "═══════════════════════════════════════════════════════════"
echo "Full file: cat $LATEST"
echo "All logs: ls -lh logs/"
