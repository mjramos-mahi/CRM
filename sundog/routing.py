from django.conf.urls import url
from django.db.models import Model
from django.utils.decorators import method_decorator
from django.views import View
from importlib import import_module
from pkgutil import walk_packages
from sys import modules


class Route:
    '''
    Route pattern assigned to a view.
    '''
    def __init__(self, regex, name):
        self.regex = regex
        self.name = name


def route(regex, name=None):
    '''
    Decorator to add route configuration to views.

    Omitting the name will derive the view name from the view object
    ``__name__``.

    Sample usage:

    # views.py
    from django.http import HttpResponse
    from django.views import View
    from django_routing import route

    @route(r'^some/route/?$')
    def some_route(request):
        return HttpResponse('Hello, world!')

    @route(r'^another/route/?$', name='second_hello')
    class AnotherRoute(View):
        def get(self, request):
            return HttpResponse("What's up, world?")

    # urls.py
    import views
    from django_routing import package_urls
    urlpatterns = package_urls(views)
    '''

    def modify(dictionary, key, default, function):
        if key not in dictionary:
            dictionary[key] = default
        dictionary[key] = function(dictionary[key])
        return dictionary

    def routed(view):
        nonlocal regex
        nonlocal name
        modify(
            modules[view.__module__].__dict__,
            Route,
            {},
            lambda module_routes:
                modify(
                    module_routes,
                    view,
                    [],
                    lambda view_routes:
                        view_routes + [Route(regex, name)]
                )
        )
        return view
    return routed


decorate_view = (
    lambda decorator:
        lambda view: (
            method_decorator(decorator, name='dispatch')(view)
            if isinstance(view, type) and issubclass(view, View)
            else decorator(view)
        )
)


filter_package_modules = lambda package, filter: [
    x
    for loader, name, is_pkg in walk_packages(package.__path__)
    for module in [import_module(package.__package__ + '.' + name)]
    for x in filter(module)
]


module_urls = lambda module: [
    url(
        regex=route.regex,
        name=(
            route.name
            if route.name
            else view.__module__ + '.' + view.__name__
        ),
        view=(
            view.as_view()
            if isinstance(view, type) and issubclass(view, View)
            else view
        ),
    )
    for view, routes in module.__dict__.get(Route, {}).items()
    for route in routes
]


package_urls = lambda package: filter_package_modules(package, module_urls)


package_models = lambda package: filter_package_modules(
    package,
    lambda module: [
        value
        for name, value in module.__dict__.items()
        if isinstance(value, type) and issubclass(value, Model)
    ]
)
