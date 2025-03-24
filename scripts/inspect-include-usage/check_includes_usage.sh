#!/bin/bash

# Directories
INCLUDES_DIR="content/includes"
CONTENT_DIR="content"

# Temp files
INCLUDE_FILES=$(mktemp)
LOG_FILE="include_analysis.log"
UNUSED_INCLUDES=$(mktemp)

# ANSI color codes (for terminal only)
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No color

# Start logging
echo "Include analysis started at $(date)" | tee "$LOG_FILE"

# Collect all include file paths (relative to INCLUDES_DIR), excluding index.md files
find "$INCLUDES_DIR" -type f | sed "s|^$INCLUDES_DIR/||" | grep -viE '(^index\.md$|/index\.md$)' > "$INCLUDE_FILES"

# Log collected files
echo "Analyzing the following include files:" >> "$LOG_FILE"
cat "$INCLUDE_FILES" >> "$LOG_FILE"

# Analyze unused includes
unused_count=0
echo -e "${RED}Unused include files:${NC}"
echo "Unused include files:" >> "$LOG_FILE"
while read -r include; do
    # Normalize paths to check with and without leading '/' and with and without '.md'
    include_with_leading_slash="/$include"
    include_without_leading_slash="$include"
    include_without_md="${include%.md}" # Remove .md if it exists

    # Grep pattern for matching all variations
    grep_pattern="({{<\s*include\s*\"(${include_with_leading_slash}|${include_without_leading_slash}|${include_without_md})\"\s*>}})"

    # Count occurrences for all variations
    count=$(grep -rE "$grep_pattern" "$CONTENT_DIR" | wc -l)

    # Debugging log
    echo "DEBUG: $include counts: $count (pattern='$grep_pattern')" >> "$LOG_FILE"

    if [ "$count" -eq 0 ]; then
        echo -e "  ${RED}$include${NC}" # Colorized for terminal
        echo "  $include" >> "$LOG_FILE" # Plain text for log
        echo "$INCLUDES_DIR/$include" >> "$UNUSED_INCLUDES"
        unused_count=$((unused_count + 1))
    fi
done < "$INCLUDE_FILES"

echo -e "${RED}Total unused includes: $unused_count${NC}"
echo "Total unused includes: $unused_count" >> "$LOG_FILE"

# Analyze includes used only once
used_once_count=0
echo ""
echo -e "${YELLOW}Include files used only once:${NC}"
echo "Include files used only once:" >> "$LOG_FILE"
while read -r include; do
    # Normalize paths to check with and without leading '/' and with and without '.md'
    include_with_leading_slash="/$include"
    include_without_leading_slash="$include"
    include_without_md="${include%.md}" # Remove .md if it exists

    # Grep pattern for matching all variations
    grep_pattern="({{<\s*include\s*\"(${include_with_leading_slash}|${include_without_leading_slash}|${include_without_md})\"\s*>}})"

    # Count occurrences for all variations
    count=$(grep -rE "$grep_pattern" "$CONTENT_DIR" | wc -l)

    # Debugging log
    echo "DEBUG: $include counts: $count (pattern='$grep_pattern')" >> "$LOG_FILE"

    if [ "$count" -eq 1 ]; then
        echo -e "  ${YELLOW}$include${NC}" # Colorized for terminal
        echo "  $include" >> "$LOG_FILE" # Plain text for log
        used_once_count=$((used_once_count + 1))
    fi
done < "$INCLUDE_FILES"

echo -e "${YELLOW}Total includes used only once: $used_once_count${NC}"
echo "Total includes used only once: $used_once_count" >> "$LOG_FILE"

# Ask user if they want to delete unused includes
if [ "$unused_count" -gt 0 ]; then
    echo ""
    read -p "Do you want to delete all unused includes? (Y/N): " delete_unused
    if [[ "$delete_unused" =~ ^[Yy]$ ]]; then
        while read -r unused_file; do
            rm -f "$unused_file"
            echo -e "Deleted: ${RED}$unused_file${NC}" # Colorized for terminal
            echo "Deleted: $unused_file" >> "$LOG_FILE" # Plain text for log
        done < "$UNUSED_INCLUDES"
        echo -e "${RED}All unused includes have been deleted.${NC}"
        echo "All unused includes have been deleted." >> "$LOG_FILE"
    else
        echo "No files were deleted."
        echo "No files were deleted." >> "$LOG_FILE"
    fi
fi

echo ""
echo "Include analysis completed at $(date)" | tee -a "$LOG_FILE"

# Cleanup
rm "$INCLUDE_FILES" "$UNUSED_INCLUDES"