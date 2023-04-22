# CalDAV Backend

Panban can read/write CalDAV VTODO tasks, which is a common standard used by
NextCloud, Outlook, Google Tasks, Tasks.org, etc., by utilizing the
[icalendar](https://icalendar.readthedocs.io) library.

The task files need to be accessible via the file system, so in order to access
remote calendars from e.g. NextCloud, you need to sync them to the file system first with an application like [vdirsyncer](https://github.com/pimutils/vdirsyncer).

Here is an example screenshot of actual panban use during panban development:

![Screenshot of Panban using CalDAV backend](screenshot_caldav.png)

And the same data as viewed on the Android app "Tasks.org":

![Screenshot of the same data from the Tasks.org app](screenshot_tasksorg.png)