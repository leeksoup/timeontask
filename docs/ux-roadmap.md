# UX Roadmap and Prioritization

This document organizes the current UX improvement ideas into a staged roadmap that balances user value, implementation effort, and dependency order.

## Prioritization principles

We should prioritize work that:

1. Improves everyday usage in the core workflow (`Today`, `Tasks`, `Projects`, `Weekly Review`).
2. Reduces friction before adding net-new feature surface area.
3. Builds reusable foundations for later features.
4. Avoids data-loss risk until delete/archive behavior is clearly defined.

## Recommended phases

### Phase 1: Quick wins in the daily workflow

These changes are high-value, low-to-medium effort, and directly improve the most frequently used screens.

1. **Today page spacing for easier completion clicks**
   - Increase row spacing / button hit area.
   - Improve mobile and laptop usability.
   - Minimal backend work.

2. **Today page task picker sorted/grouped by project**
   - Makes it easier to choose the right task quickly.
   - Pairs well with existing project-oriented planning.
   - Likely a small backend/query plus template update.

3. **Weekly Review: include completed tasks from the week**
   - Gives users a clearer sense of weekly progress.
   - Important for trust in the review flow.
   - Should distinguish between completed weekly goals and other completed tasks.

4. **Tasks page: quick-add task under each project heading**
   - Strong workflow shortcut.
   - Naturally complements project grouping.
   - Best paired with a project-grouped task list presentation.

### Phase 2: Core management improvements

These are still important, but they introduce more state-changing operations that should be done carefully.

5. **Task edit screen: add delete task action**
   - Useful, but deletion semantics should be designed first.
   - Recommendation: ship as archive/soft-delete if possible rather than hard delete.

6. **Projects: edit project names**
   - Straightforward and useful.
   - Helps clean up project lists without changing workflow semantics.

7. **Projects: click project name to start adding a task for that project**
   - Nice navigation improvement.
   - Best implemented alongside project-focused pages or filtered task views.

8. **Projects: delete project**
   - Potentially destructive because projects are connected to tasks, meetings, and goals.
   - Should come after archive/delete strategy is decided.

### Phase 3: Safety and polish foundations

These ideas reduce mistakes and improve confidence, especially once delete/archive actions exist.

9. **Soft delete / undo**
   - Recommended before broad delete support.
   - Creates safer UX for task/project removal.
   - Can become the foundation for future archive views.

10. **Overdue highlighting**
    - High visibility and useful prioritization signal.
    - Should be added after spacing and layout improvements so the UI remains readable.

11. **Duplicate task detection**
    - Helps prevent clutter when using quick-add workflows.
    - Most valuable after more task-entry shortcuts are added.

### Phase 4: Structure and deeper workflow features

These features are valuable, but they are either larger in scope or benefit from earlier cleanup.

12. **Project dashboard pages**
    - Strong long-term information architecture improvement.
    - Can unify project details, quick-add task, meetings, and progress summaries.
    - Good anchor for project-name clickthrough behavior.

13. **Snooze task until next week**
    - Useful, but should be defined carefully relative to weekly goals and today selection.
    - Possibly overlaps with carry-forward and future scheduling behavior.

14. **Drag-to-reorder subtasks**
    - Nice usability enhancement.
    - Lower urgency than improving top-level task workflows.

15. **Template-based project creation**
    - Powerful feature, but higher design complexity.
    - Best after project dashboards and duplicate handling are clearer.

### Phase 5: Admin and portability features

These are valuable, but less urgent for core day-to-day UX.

16. **.env support for easier setup**
    - Good developer/operator experience improvement.
    - Small effort and could be moved earlier if setup friction is a current blocker.

17. **Database backup helper**
    - Important operational tooling.
    - More admin-focused than end-user UX.

18. **Export/import**
    - Useful for portability and long-term confidence.
    - Better once data shape and deletion/archive semantics stabilize.

## Recommended next sprint

If we want the best near-term user impact, the next sprint should focus on:

1. Today page spacing / larger completion target.
2. Today task picker sorted or grouped by project.
3. Weekly Review showing completed tasks from the week.
4. Task quick-add under each project section on the Tasks page.

## Important design decisions before implementation

Before building the delete-related items, decide:

- Should deletion be hard delete, soft delete, or archive?
- What happens to weekly goals if a task is deleted?
- What happens to meetings linked to a project that is deleted?
- Should completed tasks appear in Weekly Review only if they were weekly goals, or all completed tasks for the week?
- Should project clickthrough lead to a filtered Tasks page or a dedicated project dashboard page?

## Suggested delivery order

### Milestone A: Daily flow polish
- Today spacing improvements.
- Today task picker grouping/sorting by project.
- Overdue highlighting (optional add-on if capacity remains).

### Milestone B: Review + task-entry improvements
- Weekly Review completed-task visibility.
- Tasks page quick-add under project headings.
- Duplicate task detection warnings.

### Milestone C: Safe editing and deletion
- Soft delete / undo foundation.
- Delete task from edit screen.
- Rename project.
- Delete/archive project.

### Milestone D: Information architecture
- Project dashboard pages.
- Project-name clickthrough navigation.
- Snooze to next week.

### Milestone E: Advanced/admin features
- Drag-to-reorder subtasks.
- Template-based project creation.
- `.env` support.
- Backup helper.
- Export/import.
