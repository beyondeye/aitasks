# Implementation Plan: aitasks-stats Skill (t39)

## Summary

Create a new Claude skill `aitasks-stats` that calculates and displays statistics for AI task completions:
- Daily completion counts
- Global statistics (7-day, 30-day, all-time)
- **Day-of-week averages** (current week, last 30 days, all-time)
- **Per-label weekly trends** (last 4 weeks)
- Per-label day-of-week averages
- **Task type weekly trends** (features/bugs, last 4 weeks)
- **Features/Bugs by label weekly trends** (last 4 weeks)
- **Export to CSV/XLS** for graphing

## Approach: Skill + Bash Script

Following the established pattern (aitask-cleanold, aitask-pick), implement:
1. **`aitask_stats.sh`** - Bash script for data collection and calculation
2. **`.claude/skills/aitasks-stats/SKILL.md`** - Skill file for invocation

## Implementation Steps

### Step 1: Create `aitask_stats.sh` Script

**Location:** `/home/ddt/Work/tubetime/aitask_stats.sh`

**Core functionality:**
1. Parse completed tasks from:
   - `aitasks/archived/*.md` (parent tasks)
   - `aitasks/archived/t*/*.md` (child tasks)
   - `aitasks/archived/old.tar.gz` (compressed archives)

2. Extract from each task:
   - `completed_at` date (YYYY-MM-DD HH:MM format)
   - `labels` array
   - `issue_type` (feature/bug)
   - Task type (parent/child from filename pattern)

3. Calculate statistics:
   - Daily counts for last N days (default 7)
   - 7-day, 30-day, all-time totals
   - **Day-of-week counts** (current week + averages for 30d/all-time)
   - **Per-label weekly trends** (last 4 weeks: W-3, W-2, W-1, This Week)
   - **Per-label day-of-week averages** (last 30 days)
   - **Task type weekly trends** (parent/child, feature/bug)
   - **Features/Bugs by label weekly trends** (last 4 weeks)

4. Output options:
   - Markdown tables (default)
   - CSV export (--csv)
   - XLS export (--xls) - requires `ssconvert` from gnumeric or Python

**Command-line options:**
- `-d, --days N` - Days for daily breakdown (default: 7)
- `-v, --verbose` - Show task IDs in daily breakdown
- `--csv [FILE]` - Export to CSV (default: aitask_stats.csv)
- `-h, --help` - Show usage

**Key functions to implement:**

```bash
# Parse completed_at from YAML frontmatter
parse_completed_at() {
    local content="$1"
    echo "$content" | grep -E "^completed_at:" | head -1 | sed 's/completed_at:[[:space:]]*//'
}

# Parse labels from YAML frontmatter
parse_labels() {
    local content="$1"
    echo "$content" | grep -E "^labels:" | head -1 | sed 's/labels:[[:space:]]*//' | tr -d '[]' | tr -d ' '
}

# Parse issue_type from YAML frontmatter
parse_issue_type() {
    local content="$1"
    echo "$content" | grep -E "^issue_type:" | head -1 | sed 's/issue_type:[[:space:]]*//'
}

# Get day of week from date (0=Sun, 1=Mon, ..., 6=Sat)
get_day_of_week() {
    local date="$1"
    date -d "$date" +%u  # 1=Mon, 7=Sun (ISO format)
}

# Calculate average per day of week
calculate_dow_average() {
    # Count tasks per day of week
    # Divide by number of weeks in period
}

# Collect tasks from all sources
collect_completed_tasks() {
    # 1. Archived parent tasks: aitasks/archived/t*_*.md
    # 2. Archived child tasks: aitasks/archived/t*/t*_*_*.md
    # 3. Compressed tasks: aitasks/archived/old.tar.gz
}

# Export to CSV
export_csv() {
    local output_file="$1"
    # Write header row
    # Write data rows for each task
    # Include: date, day_of_week, task_id, labels, issue_type, task_type
}

# Print LibreOffice import instructions
print_libreoffice_instructions() {
    echo "CSV exported. To create charts in LibreOffice:"
    echo "1. Open LibreOffice Calc"
    echo "2. File → Open → Select the CSV file"
    echo "3. Use Insert → Chart or Insert → Pivot Table for analysis"
}
```

**Handling tar.gz archives:**
```bash
# List files in archive
tar -tzf aitasks/archived/old.tar.gz 2>/dev/null | grep '\.md$' | while read -r filename; do
    content=$(tar -xzf aitasks/archived/old.tar.gz -O "$filename" 2>/dev/null)
    # Parse content...
done
```

**Output format (markdown):**
```
## Task Completion Statistics

Generated: 2026-02-04 15:30

### Summary
| Metric                    | Count |
|---------------------------|-------|
| Total Tasks Completed     | 45    |
| Completed (Last 7 days)   | 12    |
| Completed (Last 30 days)  | 32    |

### Daily Completions (Last 7 Days)
| Date       | Day | Count | Tasks                          |
|------------|-----|-------|--------------------------------|
| 2026-02-04 | Tue | 2     | t29_4, t29_3                   |
| 2026-02-03 | Mon | 3     | t33, t32, t27                  |
| ...        |     |       |                                |

### Average Completions by Day of Week
| Day       | This Week | Last 30d Avg | All-time Avg |
|-----------|-----------|--------------|--------------|
| Monday    | 2         | 1.5          | 1.2          |
| Tuesday   | 3         | 2.0          | 1.8          |
| Wednesday | 1         | 1.2          | 1.0          |
| Thursday  | -         | 0.8          | 0.9          |
| Friday    | -         | 1.0          | 0.7          |
| Saturday  | -         | 0.5          | 0.3          |
| Sunday    | -         | 0.2          | 0.1          |

### Completions by Label - Weekly Trend (Last 4 Weeks)
| Label          | Total | W-3 | W-2 | W-1 | This Week |
|----------------|-------|-----|-----|-----|-----------|
| tubetimeui     | 15    | 2   | 3   | 4   | 3         |
| claudeskills   | 8     | 1   | 2   | 2   | 2         |
| aitasks        | 6     | 1   | 1   | 2   | 1         |
| (unlabeled)    | 10    | 2   | 2   | 3   | 2         |

### Label Avg by Day of Week (Last 30 Days)
| Label        | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|--------------|-----|-----|-----|-----|-----|-----|-----|
| tubetimeui   | 0.5 | 0.8 | 0.3 | 0.2 | 0.4 | 0.1 | 0.0 |
| claudeskills | 0.3 | 0.4 | 0.2 | 0.1 | 0.2 | 0.0 | 0.0 |

### By Task Type - Weekly Trend (Last 4 Weeks)
| Type           | Total | W-3 | W-2 | W-1 | This Week |
|----------------|-------|-----|-----|-----|-----------|
| Parent Tasks   | 20    | 4   | 5   | 6   | 3         |
| Child Tasks    | 25    | 5   | 6   | 8   | 5         |
| Features       | 35    | 7   | 9   | 10  | 6         |
| Bug Fixes      | 10    | 2   | 2   | 4   | 2         |

### Features/Bugs by Label - Weekly Trend (Last 4 Weeks)
| Label        | Type    | Total | W-3 | W-2 | W-1 | This Week |
|--------------|---------|-------|-----|-----|-----|-----------|
| tubetimeui   | Feature | 12    | 2   | 2   | 3   | 2         |
| tubetimeui   | Bug     | 3     | 0   | 1   | 1   | 1         |
| claudeskills | Feature | 7     | 1   | 2   | 2   | 1         |
| claudeskills | Bug     | 1     | 0   | 0   | 0   | 1         |
```

**CSV Export Format:**
```csv
date,day_of_week,week_offset,task_id,labels,issue_type,task_type
2026-02-04,Tuesday,0,t29_4,"",feature,child
2026-02-04,Tuesday,0,t29_3,"tubetimeui,youtubescreen",feature,child
2026-02-03,Monday,0,t33,"claudeskills",bug,parent
2026-01-27,Monday,1,t30,"claudeskills,aitasks",feature,parent
...
```

The CSV contains raw data that can be imported into LibreOffice Calc for custom graphing.
- `week_offset`: 0 = this week, 1 = last week (W-1), 2 = W-2, 3 = W-3, etc.

**Importing CSV in LibreOffice Calc:**
1. Open LibreOffice Calc
2. File → Open → Select the CSV file
3. In the import dialog:
   - Character set: UTF-8
   - Separator: Comma
   - Check "Quoted field as text"
4. Click OK

**Creating Charts in LibreOffice:**
1. Select the data range (e.g., date and count columns)
2. Insert → Chart
3. Choose chart type (Line, Bar, or XY Scatter for trends)
4. Follow the wizard to customize

**Pivot Tables for Analysis:**
1. Select all data
2. Insert → Pivot Table
3. Drag fields:
   - Row: `week_offset` or `day_of_week`
   - Column: `labels` or `issue_type`
   - Data: Count of `task_id`
4. Creates summary table for trends

### Step 2: Create Skill File

**Location:** `/home/ddt/Work/tubetime/.claude/skills/aitasks-stats/SKILL.md`

```yaml
---
name: aitasks-stats
description: Calculate and display statistics of AI task completions (daily, global, per-label).
---

## Usage

Run the statistics script:

\`\`\`bash
./aitask_stats.sh [OPTIONS]
\`\`\`

### Options

- `-d, --days N` - Show daily breakdown for last N days (default: 7)
- `-v, --verbose` - Show individual task IDs in daily breakdown
- `--csv [FILE]` - Export raw data to CSV (default: aitask_stats.csv)
- `-h, --help` - Show usage information

### Examples

Basic statistics (last 7 days):
\`\`\`bash
./aitask_stats.sh
\`\`\`

Extended daily view (14 days):
\`\`\`bash
./aitask_stats.sh --days 14
\`\`\`

Verbose output with task names:
\`\`\`bash
./aitask_stats.sh -v
\`\`\`

Export to CSV for graphing in LibreOffice:
\`\`\`bash
./aitask_stats.sh --csv
\`\`\`

## Statistics Provided

1. **Summary** - Total completions, 7-day and 30-day counts
2. **Daily Breakdown** - Completions per day with optional task IDs
3. **Day of Week Stats** - Current week counts + 30d/all-time averages per weekday
4. **Label Weekly Trends** - Per-label completions for last 4 weeks (W-3, W-2, W-1, This Week)
5. **Label Day-of-Week Breakdown** - Per-label averages by day of week
6. **Task Type Weekly Trends** - Parent/child and feature/bug trends for last 4 weeks
7. **Features/Bugs by Label Trends** - Combined label + issue type weekly trends

## Export Format

**CSV Export:** Raw task data with columns:
- date, day_of_week, week_offset, task_id, labels, issue_type, task_type

Open in LibreOffice Calc to create custom charts and pivot tables for trend analysis.
```

### Step 3: Make Script Executable

```bash
chmod +x aitask_stats.sh
```

### Step 4: Update settings.local.json (if needed)

Add permission for the new script to `.claude/settings.local.json`:
```json
"Bash(./aitask_stats.sh:*)"
```

## Files to Create/Modify

| File | Action |
|------|--------|
| `aitask_stats.sh` | CREATE - Main statistics script |
| `.claude/skills/aitasks-stats/SKILL.md` | CREATE - Skill definition |
| `.claude/settings.local.json` | MODIFY - Add script permission (if not auto-allowed) |

## Reference Files

- **YAML parsing pattern:** `aitask_ls.sh:165-231` - `parse_yaml_frontmatter()` function
- **Skill format:** `.claude/skills/aitask-cleanold/SKILL.md` - Simple skill that invokes a script
- **Archive handling:** `aitask_clear_old.sh` - Pattern for working with old.tar.gz

## Data Structures

```bash
# Day-of-week tracking
declare -A dow_counts_thisweek    # day_num -> count (current week only)
declare -A dow_counts_30d         # day_num -> count (last 30 days)
declare -A dow_counts_total       # day_num -> count (all time)

# Per-label day-of-week
declare -A label_dow_counts_30d   # "label:dow" -> count

# Weekly trend tracking (last 4 weeks)
declare -A label_week_counts      # "label:week_offset" -> count (week_offset: 0=this week, 1=W-1, 2=W-2, 3=W-3)
declare -A type_week_counts       # "type:week_offset" -> count (type: parent|child|feature|bug)
declare -A label_type_week_counts # "label:type:week_offset" -> count
```

**Week offset calculation:**
```bash
# Get week start date (Monday) for a given date
get_week_start() {
    local date="$1"
    local dow=$(date -d "$date" +%u)  # 1=Mon, 7=Sun
    date -d "$date - $((dow - 1)) days" +%Y-%m-%d
}

# Get week offset from current week (0 = this week, 1 = last week, etc.)
get_week_offset() {
    local completed_date="$1"
    local today="$2"
    local completed_week_start=$(get_week_start "$completed_date")
    local current_week_start=$(get_week_start "$today")

    # Calculate difference in days and convert to weeks
    local diff_days=$(( ($(date -d "$current_week_start" +%s) - $(date -d "$completed_week_start" +%s)) / 86400 ))
    echo $((diff_days / 7))
}

# Only track tasks from weeks 0-3 (this week and 3 previous)
week_offset=$(get_week_offset "$completed_date" "$today")
if [[ $week_offset -ge 0 && $week_offset -le 3 ]]; then
    ((label_week_counts["$label:$week_offset"]++))
    ((type_week_counts["$issue_type:$week_offset"]++))
    ((label_type_week_counts["$label:$issue_type:$week_offset"]++))
fi
```

**Day of week calculation:**
```bash
# Get ISO day of week (1=Monday, 7=Sunday)
dow=$(date -d "$completed_date" +%u 2>/dev/null)

# Map to day name
day_names=("" "Mon" "Tue" "Wed" "Thu" "Fri" "Sat" "Sun")
day_name="${day_names[$dow]}"

# Track current week separately
current_week_start=$(get_week_start "$today")
completed_week_start=$(get_week_start "$completed_date")
if [[ "$completed_week_start" == "$current_week_start" ]]; then
    ((dow_counts_thisweek[$dow]++))
fi
```

**Averaging logic:**
```bash
# Count number of each weekday in the last 30 days
for ((i=0; i<30; i++)); do
    check_date=$(date -d "$today - $i days" +%Y-%m-%d)
    dow=$(date -d "$check_date" +%u)
    ((dow_occurrences[$dow]++))
done

# Average = count / occurrences
for dow in {1..7}; do
    avg=$(echo "scale=1; ${dow_counts_30d[$dow]:-0} / ${dow_occurrences[$dow]:-1}" | bc)
done
```

## Edge Cases to Handle

1. **Missing `completed_at`** - Skip task or fallback to `updated_at` if status is Done
2. **Empty labels `[]`** - Count as "(unlabeled)"
3. **Malformed dates** - Skip and log warning
4. **Empty archive** - Handle gracefully, show zero counts
5. **No completed tasks** - Show message indicating no data

## Verification

After implementation:

```bash
# Test basic output
./aitask_stats.sh

# Test with different day counts
./aitask_stats.sh -d 1
./aitask_stats.sh -d 30

# Test verbose mode
./aitask_stats.sh -v

# Test CSV export
./aitask_stats.sh --csv
cat aitask_stats.csv
# Open in LibreOffice Calc to verify import

# Verify help
./aitask_stats.sh -h

# Verify all archived tasks are counted
# (manually count files in archived/ and old.tar.gz for comparison)
```
