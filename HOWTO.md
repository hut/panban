# How-Tos

This document describes step-by-step instructions for solving common problems.

## Sorting Tags

**Compatible backends**: caldav, markdown

**Problem**: If you have many tags, it becomes inconvenient to navigate them, and you might lose sight of the most important tags, since they are sorted alphabetically by default.

**Solution**: Assign priorities to tags in the tag list ("q" key) through the following method:

1. Create a new task in your panban board called "Tag Priorities". (This is a special keyword)
2. Open the description of the task by pressing "E".
3. Write a description like the following: (details below)

```markdown
# High

- tag1
- tag2

# Medium
# Low

- tag3

# None
```

4. Save the description and open the tag menu with "q" to observe that the tags you put under "# High" are now at the top and all other tags are sorted accordingly as well.


Once this is set up, it gets much easier to change tag priorities:

1. Navigate to the "Tag Priorities" task
2. Press "B" to open the description as a markdown sub-board in a new panban instance
3. Move the tags around as needed, as if they are regular tasks
4. Press "Q" to save the description and return to the base panban instance

### Details

- The description of "Tag Priorities" must be a valid panban board in markdown format
    - Each line like "# High" defines a column
    - Each line like "- tag1" defines an item in that column
- The only columns with any effect are "High", "Medium", "Low", and "None". You can add any others but they will be ignored for the purpose of prioritizing tags.
- A tag's default priority is "Medium".
- You can leave out any column or any tag that you don't need. A file like this is completely valid too:

```markdown
# High

- tag1
```

- But it makes sense to add all the columns so you can easily change the priorities with the "B" key as described above.
- It would have been preferable to assign the priority as an attribute to the tag directly, but in most backends, tags are mere strings without additional metadata. This is why this cumbersome method has been chosen, which works equally well on all backends that implement descriptions.
