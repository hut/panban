import datetime
import os.path
import subprocess
import sys
import uuid
import panban.api
from panban.json_api import exceptions
from panban.json_api.eternal import PortableResponse, PortableNode

COL_TODO = '__todo'
COL_TODAY = '__today'
COL_DONE = '__done'
COL_LABEL_TODO = 'Todo'
COL_LABEL_TODAY = 'Active'
COL_LABEL_DONE = 'DONE'
COL_ID_TODO = 0
COL_ID_TODAY = 1
COL_ID_DONE = 2

SHOW_COMPLETED_ITEMS_FOR_DAYS = 14

CATEGORY_PREFIX = '__category_'
ROOT_CATEGORY = '__all'

VTODO_STATUS_TODO = 'NEEDS-ACTION'
VTODO_STATUS_DONE = 'COMPLETED'
VTODO_PRIO_MAP = {
    0: None,
    1: 9,
    2: 5,
    3: 1,
}
VTODO_PRIO_MAP_REVERSE = dict((val, key) for (key, val) in VTODO_PRIO_MAP.items())

ISO_DATE = '%Y-%m-%d'

class Handler(panban.api.Handler):
    def response(self, data=None, status=None):
        if status is None:
            status = PortableResponse.STATUS_OK

        response = PortableResponse(
            version=self.json_api.VERSION,
            status=status,
            data=data,
        )
        return response

    def cmd_getcolumndata(self, query):
        self.load_data(query.source)
        return self.response(self.nodes_by_id)

    def cmd_changelabel(self, query):
        self.load_data(query.source)

        uid = query.arguments['item_id']
        vtodo = self.vtodos_by_id[uid]
        old_label = str(vtodo['summary'])
        new_label = query.arguments['new_label']
        if old_label != new_label:
            vtodo['summary'] = new_label
            self._write_vtodo(vtodo)

        return self.response()

    def cmd_changeprio(self, query):
        self.load_data(query.source)

        uid = query.arguments['item_id']
        vtodo = self.vtodos_by_id[uid]
        old_value = vtodo.get('priority', None)
        new_value_raw = query.arguments['prio']
        new_value = VTODO_PRIO_MAP[new_value_raw]
        if old_value != new_value:
            if new_value is None:
                del vtodo['priority']
            else:
                vtodo['priority'] = new_value
            self._write_vtodo(vtodo)

        return self.response()

    def cmd_changetags(self, query):
        import icalendar

        # Extract relevant data from query and cache
        self.load_data(query.source)
        uid = query.arguments['item_id']
        vtodo = self.vtodos_by_id[uid]
        if 'categories' in vtodo:
            old_value = [str(cat) for cat in vtodo['categories'].cats]
        else:
            old_value = []
        new_value = list(old_value)
        target_tags = query.arguments['tags']
        action = query.arguments['action']

        # Apply the requested action
        if action == self.json_api.PARAM_TAG_ADD:
            for tag in target_tags:
                if tag not in new_value:
                    new_value.append(tag)
        elif action == self.json_api.PARAM_TAG_REMOVE:
            for tag in target_tags:
                if tag in new_value:
                    new_value.remove(tag)
        elif action == self.json_api.PARAM_TAG_CLEAR:
            new_value = []

        if old_value != new_value:
            vtodo['categories'] = icalendar.prop.vCategory(new_value)
            self._write_vtodo(vtodo)

        return self.response()

    def cmd_addnode(self, query):
        import icalendar

        vtodo = icalendar.Todo()
        vtodo['summary'] = query.arguments['label']
        vtodo['created'] = icalendar.vDatetime(datetime.datetime.now())
        vtodo['uid'] = uid = str(uuid.uuid4())

        path = os.path.join(self.basedir, '%s.ics' % uid)
        if os.path.exists(path):
            raise Exception('Path already exists: %s' % path)

        # Infer metadata from column
        column_id = query.arguments['target_column']
        column = self.nodes_by_id[column_id]
        if column.label == COL_LABEL_TODO:
            vtodo['status'] = VTODO_STATUS_TODO
        elif column.label in (COL_LABEL_TODAY, COL_LABEL_DONE):
            vtodo['status'] = VTODO_STATUS_TODO
            vtodo['due'] = icalendar.vDatetime(datetime.datetime.now())

        # Set tag
        category_id = column.parent
        if category_id != (CATEGORY_PREFIX + ROOT_CATEGORY):
            category = self.nodes_by_id[category_id]
            vtodo['categories'] = icalendar.prop.vCategory([category.label])

        node = self.make_node(
            uid=uid,
            label=vtodo['summary'],
            parent=category_id,
        )

        self.vtodos_by_id[uid] = vtodo
        self.node_id_to_path[uid] = path
        self.nodes_by_id[uid] = node
        column.children.append(uid)

        self._write_vtodo(vtodo, create=True)
        return self.response()

    def cmd_deleteitems(self, query):
        self.load_data(query.source)
        paths = []
        for uid in query.arguments['item_ids']:
            path = self.node_id_to_path[uid]
            paths.append(path)

        for path in paths:
            os.unlink(path)

        return self.response()

    def cmd_moveitemstocolumn(self, query):
        import icalendar
        ids = query.arguments['item_ids']
        dirty = []
        
        # Check whether we need to do any changes
        for uid in query.arguments['item_ids']:
            vtodo = self.vtodos_by_id[uid]
            if query.arguments['target_column'].endswith(COL_DONE):
                if str(vtodo.get('status', '')) != VTODO_STATUS_DONE:
                    dirty.append(vtodo)
            elif query.arguments['target_column'].endswith(COL_TODAY):
                if not self._is_due_today(vtodo):
                    dirty.append(vtodo)
                if str(vtodo.get('status', '')) != VTODO_STATUS_TODO:
                    dirty.append(vtodo)
            else:
                if self._is_due_today(vtodo):
                    dirty.append(vtodo)
                if str(vtodo.get('status', '')) != VTODO_STATUS_TODO:
                    dirty.append(vtodo)

        if not dirty:
            # Nothing to do.
            return self.response()

        # Reload data in case of changes since last reload
        self.load_data(query.source)
        dirty = []

        # Apply changes
        now = icalendar.vDatetime(datetime.datetime.now())
        for uid in query.arguments['item_ids']:
            vtodo = self.vtodos_by_id[uid]
            if query.arguments['target_column'].endswith(COL_DONE):
                # Requirements for it to show up in the "Done" column:
                # - Task completed
                # Make sure that these requirements are met:
                if str(vtodo.get('status', '')) != VTODO_STATUS_DONE:
                    vtodo['status'] = VTODO_STATUS_DONE
                    vtodo['completed'] = now
                    if vtodo not in dirty: dirty.append(vtodo)

            elif query.arguments['target_column'].endswith(COL_TODAY):
                # Requirements for it to show up in the "Active" column:
                # - Due today or earlier
                # - Not completed yet
                # Make sure that these requirements are met:
                if not self._is_due_today(vtodo):
                    vtodo['due'] = now
                    if vtodo not in dirty: dirty.append(vtodo)
                if str(vtodo.get('status', '')) != VTODO_STATUS_TODO:
                    vtodo['status'] = VTODO_STATUS_TODO
                    if 'completed' in vtodo:
                        del vtodo['completed']
                    if vtodo not in dirty: dirty.append(vtodo)

            else:
                # Requirements for it to show up in the "Todo" column:
                # - No due date or due date later than tomorrow
                # - Not completed yet
                # Make sure that these requirements are met:
                if self._is_due_today(vtodo):
                    del vtodo['due']
                    if vtodo not in dirty: dirty.append(vtodo)
                if str(vtodo.get('status', '')) != VTODO_STATUS_TODO:
                    vtodo['status'] = VTODO_STATUS_TODO
                    if 'completed' in vtodo:
                        del vtodo['completed']
                    if vtodo not in dirty: dirty.append(vtodo)

        for vtodo in dirty:
            self._write_vtodo(vtodo)

        return self.response()

    def load_data(self, basedir):
        if not os.path.exists(basedir):
            raise exceptions.SourceFileDoesNotExist(basedir)

        import icalendar

        ics_files = [filename for filename in os.listdir(basedir) \
                if filename.lower().endswith('.ics')]

        self.basedir = basedir
        self.nodes_by_id = {}
        self.vtodos_by_id = {}
        self.node_id_to_path = {}
        self.categories = {}

        def add_category(label, key=None, prio=0):
            # use "key" for internal categories where key != label, e.g. "__all"
            if key is None:
                key = label

            category_uid = CATEGORY_PREFIX + key
            category_node = self.make_node(
                uid=category_uid,
                label=label,
                parent=None,
                prio=prio,
            )
            self.nodes_by_id[category_node.id] = category_node

            column_todo = self.make_node(
                uid=category_uid + COL_TODO,
                label=COL_LABEL_TODO,
                parent=category_uid,
                pos=0,
            )
            self.nodes_by_id[column_todo.id] = column_todo
            category_node.children.append(column_todo.id)

            column_today = self.make_node(
                uid=category_uid + COL_TODAY,
                label=COL_LABEL_TODAY,
                parent=category_uid,
                pos=0,
            )
            self.nodes_by_id[column_today.id] = column_today
            category_node.children.append(column_today.id)

            column_done = self.make_node(
                uid=category_uid + COL_DONE,
                label=COL_LABEL_DONE,
                parent=category_uid,
                pos=1,
            )
            self.nodes_by_id[column_done.id] = column_done
            category_node.children.append(column_done.id)

            self.categories[key] = category_node

        # First of all, add a category that every node will belong to
        add_category('All Entries', ROOT_CATEGORY, 3)

        # Then add a node for every ICS file in the directory, along with extra categories
        for filename in ics_files:
            path = os.path.join(basedir, filename)
            uid, vtodo = self._extract_vtodo(path)
            status = str(vtodo.get('status', None))
            if 'due' in vtodo:
                due_date = vtodo['due'].dt.strftime(ISO_DATE)
                today = datetime.date.today().strftime(ISO_DATE)
            else:
                due_date = None

            if status == VTODO_STATUS_DONE:
                column_index = COL_ID_DONE

                # Hide completed items that are older than N days
                if 'completed' in vtodo:
                    completed_day = vtodo['completed'].dt.strftime(ISO_DATE)
                    cutoff_day = datetime.date.today() - datetime.timedelta(SHOW_COMPLETED_ITEMS_FOR_DAYS)
                    if completed_day < cutoff_day.strftime(ISO_DATE):
                        continue
            elif self._is_due_today(vtodo):
                column_index = COL_ID_TODAY
            else:
                column_index = COL_ID_TODO

            if 'categories' in vtodo:
                categories_internal = vtodo['categories']
                categories = [str(cat) for cat in categories_internal.cats]
            else:
                categories = []

            pnode = self.make_node(
                uid=uid,
                label=str(vtodo['summary']),
                parent=self.categories[ROOT_CATEGORY].children[column_index],
                prio=VTODO_PRIO_MAP_REVERSE[vtodo.get('priority', None)],
            )
            self.nodes_by_id[uid] = pnode
            self.vtodos_by_id[uid] = vtodo
            self.node_id_to_path[uid] = path

            # Add the node to its categories. Create categories that don't exist.
            for category_label in [ROOT_CATEGORY] + categories:
                if category_label not in self.categories:
                    add_category(category_label)
                category = self.categories[category_label]
                column = self.nodes_by_id[category.children[column_index]]
                column.children.append(pnode.id)

    def _extract_vtodo(self, path):
        import icalendar
        with open(path, 'r') as f:
            content = f.read()

        # The root component of an .ics file is a VCALENDAR and
        # typically the first subcomponent is the actual VTODO item.
        # Let's extract that.
        vcalendar = icalendar.Todo.from_ical(content)
        if vcalendar.name == 'VTODO':
            vtodo = vcalendar
        else:
            for component in vcalendar.subcomponents:
                if component.name == 'VTODO':
                    vtodo = component
                    break
            else:
                return
        uid = str(vtodo['uid'])
        return uid, vtodo

    def _write_vtodo(self, vtodo, create=False):
        import icalendar

        vtodo['last-modified'] = icalendar.vDatetime(datetime.datetime.now())

        uid = str(vtodo['uid'])
        path = self.node_id_to_path[uid]

        if not create:
            with open(path, 'r') as f:
                content = f.read()

            # We got the VTODO item as method argument, but the root
            # component of an .ics file is a VCALENDAR.
            # Let's extract that, and then swap out the old VTODO with
            # the new one we got as method argument.
            vcalendar = icalendar.Todo.from_ical(content)
            if vcalendar.name == 'VTODO':
                vcalendar = vtodo
            else:
                for i, component in enumerate(vcalendar.subcomponents):
                    if component.name == 'VTODO':
                        vcalendar.subcomponents[i] = vtodo
                        break
                else:
                    vcalendar.subcomponents.append(vtodo)
        else:
            vcalendar = icalendar.Calendar()
            vcalendar['version'] = '2.0'
            vcalendar['prodid'] = 'Panban'
            vcalendar.add_component(vtodo)

        content = vcalendar.to_ical().decode('utf-8')

        with open(path, 'w') as f:
            f.write(content)

    def _is_due_today(self, vtodo):
        if 'due' not in vtodo:
            return None
        due_date = vtodo['due'].dt.strftime(ISO_DATE)
        today = datetime.date.today().strftime(ISO_DATE)
        return due_date <= today

    def make_node(self, uid, label, parent, pos=None, prio=0, completion_date=None):
        pnode = PortableNode()
        pnode.label = label
        pnode.id = uid
        pnode.pos = pos
        pnode.prio = prio
        pnode.parent = parent
        return pnode

    def handle(self, query):
        command = query.command
        if command == 'load_all':
            response = self.cmd_getcolumndata(query)
        elif command == 'move_nodes':
            response = self.cmd_moveitemstocolumn(query)
        elif command == 'delete_nodes':
            response = self.cmd_deleteitems(query)
        elif command == 'change_label':
            response = self.cmd_changelabel(query)
        elif command == 'change_prio':
            response = self.cmd_changeprio(query)
        elif command == 'change_tags':
            response = self.cmd_changetags(query)
        elif command == 'add_node':
            response = self.cmd_addnode(query)
        elif command == 'sync':
            subprocess.check_call(['vdirsyncer', 'sync'])
            response = self.response()
        else:
            raise exceptions.InvalidCommandError(command)
        return response.to_json()


if __name__ == '__main__':
    if '--doctest' in sys.argv:
        import doctest
        doctest.testmod()
    else:
        handler = Handler()
        raise SystemExit(handler.main_with_error_handling(sys.stdin))
