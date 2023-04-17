import os.path
import sys
import panban.api
from panban.json_api import exceptions
from panban.json_api.eternal import PortableResponse, PortableNode

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

    def load_data(self, basedir):
        if not os.path.exists(basedir):
            raise exceptions.SourceFileDoesNotExist(basedir)

        import icalendar

        ics_files = [filename for filename in os.listdir(basedir) \
                if filename.lower().endswith('.ics')]

        self.nodes_by_id = {}

        root_node = self.make_node(
            uid='__root',
            label='all',
            parent=None,
        )
        self.nodes_by_id[root_node.id] = root_node

        column_todo = self.make_node(
            uid='__todo',
            label='Todo',
            parent=root_node.id,
            pos=0,
        )
        self.nodes_by_id[column_todo.id] = column_todo
        root_node.children.append(column_todo.id)

        column_done = self.make_node(
            uid='__done',
            label='Done',
            parent=root_node.id,
            pos=1,
        )
        self.nodes_by_id[column_done.id] = column_done
        root_node.children.append(column_done.id)

        for filename in ics_files:
            path = os.path.join(basedir, filename)
            uid, vtodo = self._extract_todo(path)

            parent = column_todo
            if str(vtodo.get('status', None)) == 'COMPLETED':
                parent = column_done

            pnode = self.make_node(
                uid=uid,
                label=str(vtodo['summary']),
                parent=parent.id,
            )
            self.nodes_by_id[uid] = pnode
            parent.children.append(pnode.id)

    def _extract_todo(self, path):
        import icalendar
        with open(path, 'r') as f:
            content = f.read()
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
