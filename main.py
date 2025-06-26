import cherrypy
import wsgiref.handlers

class Root:
    @cherrypy.expose
    def index(self):
        return "Hello, CherryPy from Google App Engine!"

if True or __name__ == '__main__':

    # This ?? from search -- cherry py app wsgi main
    # Mount the CherryPy application to get a WSGI callable
    #1 myapp = cherrypy.tree.mount(Root())
    # You can then use this 'application' callable with any WSGI server.
    # For example, if using Gunicorn:
    # gunicorn -w 4 your_module:myapp
    #2
    cherrypy.tree.mount(Root())
    myapp = cherrypy.tree

    # Use the following configuration for App Engine.
    # It's important to bind to 0.0.0.0 to listen on all interfaces
    # and to set the port to 8080 as required by App Engine.
    cherrypy.config.update({'server.socket_host': '0.0.0.0',
                            'server.socket_port': 8080})

# if __name__ == '__main__':
#     cherrypy.quickstart(Root())
