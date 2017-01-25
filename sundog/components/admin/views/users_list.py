from datatableview import Datatable, DisplayColumn, TextColumn, BooleanColumn, DateColumn
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.template.defaultfilters import date
from django.template.loader import render_to_string
from sundog.models import Company
from sundog.routing import route, decorate_view
from sundog.util.views import SundogDatatableView


@route(r'^user/?$', name='users_list')
@decorate_view(login_required)
class UsersList(SundogDatatableView):
    template_name = 'admin/users_list.html'

    model = User

    searchable_columns = [
        'name',
    ]

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu_page'] = 'admin'
        return context

    def get_queryset(self):
        return User.objects.prefetch_related('company').prefetch_related('groups').prefetch_related('userprofile').all()

    class datatable_class(Datatable):
        status = TextColumn(
            label='Active',
            source='is_active',
            processor=lambda instance, *_, **__: '<span class="glyphicon glyphicon-user' + (' green' if instance.is_active else ' red') + '"></span>',
        )
        full_name = TextColumn(
            label='Full Name',
            processor=lambda instance, *_, **__: instance.get_full_name(),
        )

        role = TextColumn(
            label='Role',
            source='groups__name',
            processor=lambda instance, *_,  **__:
                instance.groups.all().first().name if instance.groups.all().first() else '',
        )

        company = TextColumn(
            label='Company',
            source='company__name',
            processor=lambda instance, *_, **__: instance.company.name if instance.company else '',
        )

        last_login = DateColumn(
            label='Last Login',
            source='userprofile__last_login',
            processor=lambda instance, *_, **__: date(instance.userprofile.last_login, 'SHORT_DATETIME_FORMAT') if instance.userprofile else '',
        )

        actions = DisplayColumn(
            label='',
            processor=(
                lambda instance, *_, **__:
                render_to_string(
                    template_name='admin/partials/user_actions_template.html',
                    context={
                        'user_id': instance.id,
                    },
                )
            ),
        )

        class Meta:
            structure_template = 'datatableview/bootstrap_structure.html'

            columns = [
                'status',
                'username',
                'full_name',
                'email',
                'role',
                'company',
                'last_login',
                'actions',
            ]

            ordering = ['name']
