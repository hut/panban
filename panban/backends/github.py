import sys
import json
import panban.api
from panban.json_api.eternal import PortableResponse, PortableNode
from panban.json_api import exceptions
import urllib.request

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

    def load_data(self, source):
        owner, repo = source.split('/', 1)
        req = urllib.request.Request('https://api.github.com/repos/{owner}/{repo}/issues?per_page=10000&state=all'.format(owner=owner, repo=repo))
        response = urllib.request.urlopen(req).read()
        decoded = json.loads(response.decode('utf-8'))

        nodes_by_id = {}

        project_node = self.make_node(
            node_id='__root',
            label='all',
            parent=None,
        )
        nodes_by_id[project_node.id] = project_node

        column_todo = self.make_node(
            node_id='__todo',
            label='Todo',
            parent=project_node,
        )
        nodes_by_id[column_todo.id] = column_todo
        project_node.children.append(column_todo.id)

        column_active = self.make_node(
            node_id='__active',
            label='Active',
            parent=project_node,
            pos=1,
        )
        nodes_by_id[column_active.id] = column_active
        project_node.children.append(column_active.id)

        column_done = self.make_node(
            node_id='__done',
            label='Done',
            parent=project_node,
            pos=2,
        )
        nodes_by_id[column_done.id] = column_done
        project_node.children.append(column_done.id)

        for issue in decoded:
            if issue['state'] == 'open':
                if issue['comments'] > 0:
                    target_column = column_active
                else:
                    target_column = column_todo
            else:
                target_column = column_done
            node = self.make_node(
                node_id=issue['node_id'],
                label=issue['title'],
                parent=target_column,
                pos=len(target_column.children),
            )
            target_column.children.append(node.id)
            nodes_by_id[node.id] = node

        self.nodes_by_id = nodes_by_id

    def make_node(self, node_id, label, parent, pos=0, prio=2,
                creation_date=None, completion_date=None):
        if isinstance(parent, PortableNode):
            parent_id = parent.id
        elif isinstance(parent, str):
            parent_id = parent
        else:
            parent_id = ''
        pnode = PortableNode()
        pnode.label = label
        pnode.parent = parent_id
        pnode.pos = pos
        pnode.prio = prio
        pnode.id = node_id
        pnode.creation_date = creation_date
        pnode.completion_date = completion_date
        return pnode

    def handle(self, query):
        command = query.command
        if command == 'load_all':
            response = self.cmd_getcolumndata(query)
        #elif command == 'move_nodes':
        #    response = self.cmd_moveitemstocolumn(query)
        #elif command == 'delete_nodes':
        #    response = self.cmd_deleteitems(query)
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
