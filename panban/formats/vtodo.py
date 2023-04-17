import datetime
import os.path
import subprocess
import sys
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

VTODO_STATUS_TODO = 'NEEDS-ACTION'
VTODO_STATUS_DONE = 'COMPLETED'

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

    def cmd_moveitemstocolumn(self, query):
        ids = query.arguments['item_ids']
        dirty = []
        
        # Check whether we need to do any changes
        for uid in query.arguments['item_ids']:
            vtodo = self.vtodos_by_id[uid]
            if query.arguments['target_column'].endswith(COL_DONE):
                if str(vtodo.get('status', '')) != VTODO_STATUS_DONE:
                    dirty.append(vtodo)
            else:
                if str(vtodo.get('status', '')) != VTODO_STATUS_TODO:
                    dirty.append(vtodo)

        if not dirty:
            # Nothing to do.
            return self.response()

        # Reload data in case of changes since last reload
        self.load_data(query.source)
        dirty = []

        # Apply changes
        for uid in query.arguments['item_ids']:
            vtodo = self.vtodos_by_id[uid]
            if query.arguments['target_column'].endswith(COL_DONE):
                if str(vtodo.get('status', '')) != VTODO_STATUS_DONE:
                    vtodo['status'] = VTODO_STATUS_DONE
                    if vtodo not in dirty:
                        dirty.append(vtodo)
            else:
                if str(vtodo.get('status', '')) != VTODO_STATUS_TODO:
                    vtodo['status'] = VTODO_STATUS_TODO
                    if vtodo not in dirty:
                        dirty.append(vtodo)

        for vtodo in dirty:
            self._write_vtodo(vtodo)

        return self.response()

    def load_data(self, basedir):
        if not os.path.exists(basedir):
            raise exceptions.SourceFileDoesNotExist(basedir)

        import icalendar

        ics_files = [filename for filename in os.listdir(basedir) \
                if filename.lower().endswith('.ics')]

        self.nodes_by_id = {}
        self.vtodos_by_id = {}
        self.node_id_to_path = {}
        self.categories = {}

        def add_category(label, key=None):
            # use "key" for internal categories where key != label, e.g. "__all"
            if key is None:
                key = label

            category_uid = '__category_' + key
            category_node = self.make_node(
                uid=category_uid,
                label=label,
                parent = None,
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
        add_category('All Entries', '__all')

        # Then add a node for every ICS file in the directory, along with extra categories
        for filename in ics_files:
            path = os.path.join(basedir, filename)
            uid, vtodo = self._extract_vtodo(path)
            status = str(vtodo.get('status', None))
            if 'due' in vtodo:
                due_date = vtodo['due'].dt.strftime("%Y-%m-%d")
                today = datetime.date.today().strftime("%Y-%m-%d")
            else:
                due_date = None

            if status == VTODO_STATUS_DONE:
                column_index = COL_ID_DONE
            elif due_date and due_date <= today:
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
                parent=self.categories['__all'].children[column_index],
            )
            self.nodes_by_id[uid] = pnode
            self.vtodos_by_id[uid] = vtodo
            self.node_id_to_path[uid] = path

            # Add the node to its categories. Create categories that don't exist.
            for category_label in ['__all'] + categories:
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

    def _write_vtodo(self, vtodo):
        import icalendar

        uid = str(vtodo['uid'])
        path = self.node_id_to_path[uid]

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

        content = vcalendar.to_ical().decode('utf-8')
        with open(path, 'w') as f:
            f.write(content)

    def make_node(self, uid, label, parent, pos=None, completion_date=None):
        pnode = PortableNode()
        pnode.label = label
        pnode.id = uid
        pnode.pos = pos
        pnode.parent = parent
        return pnode

    def handle(self, query):
        command = query.command
        if command == 'load_all':
            response = self.cmd_getcolumndata(query)
        elif command == 'move_nodes':
            response = self.cmd_moveitemstocolumn(query)
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
