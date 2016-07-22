import copy
import json
from django.core.paginator import Paginator
from django_auth_app.utils import serialize_user
from django.shortcuts import render_to_response, redirect
from django.template.context import RequestContext
from django.contrib.auth.decorators import permission_required, user_passes_test, login_required
from django.http import Http404, StreamingHttpResponse
from django.http.response import HttpResponse, HttpResponseRedirect, JsonResponse
from django.core.urlresolvers import reverse
from django.utils.html import strip_tags
from django.core.files import File
import settings
import os
import logging
from sundog import services
from sundog import utils
from sundog import messages
from sundog.cache.user.info import get_cache_user
from sundog.constants import IMPORT_FILE_EXCEL_FILENAME, IMPORT_CLIENT_EXCEL_FILENAME
from django.contrib.auth.models import Permission
from haystack.generic_views import SearchView
from sundog.decorators import bypass_impersonation_login_required
from sundog.forms import FileCustomForm, FileSearchForm, ContactForm, ImpersonateUserForm, StageForm, StatusForm, \
    CampaignForm, SourceForm, ContactStatusForm
from datetime import datetime
from sundog.messages import MESSAGE_REQUEST_FAILED_CODE, CODES_TO_MESSAGE
from sundog.models import MyFile, Message, Document, FileStatusHistory, Contact, Stage, STAGE_TYPE_CHOICES, Status, \
    Campaign
from sundog.services import reorder_stages, reorder_status

logger = logging.getLogger(__name__)


def _render_response(request, context_info, template_path):
    context = RequestContext(request, context_info)
    return render_to_response(template_path, context_instance=context)


def index(request):
    context_info = {'request': request, 'user': request.user}
    if settings.INDEX_PAGE.endswith(".html"):
        return _render_response(request, context_info, settings.INDEX_PAGE)
    else:
        return HttpResponseRedirect(settings.INDEX_PAGE)


@bypass_impersonation_login_required
def files_recent(request):
    recent_files_list = services.get_access_file_history(request.user)
    context_info = {'request': request, 'user': request.user, 'recent_files_list': recent_files_list}
    return _render_response(request, context_info, 'file/recent_files.html')


@bypass_impersonation_login_required
def help(request):
    context_info = {'request': request, 'user': request.user}
    return _render_response(request, context_info, 'file/recent_files.html')


def terms(request):
    return render_to_response('sundog/terms.html')


def render404(request):
    return render_to_response('404.html')


@bypass_impersonation_login_required
@user_passes_test(lambda u: u.is_superuser)
def display_log(request):
    try:
        log_file_path = os.path.join(settings.PROJECT_ROOT, 'log/sundog.log')
        content = open(log_file_path, 'r').read()
        response = StreamingHttpResponse(content)
        response['Content-Type'] = 'text/plain; charset=utf8'
        return response
    except Exception as e:
        logger.error("An error occurred trying to display the log.")
        logger.error(str(e))
        return HttpResponseRedirect(reverse("admin:index"))


@permission_required('auth.impersonate_user')
def impersonate_user(request):
    post_data = request.POST
    form = ImpersonateUserForm(id=request.user.id)
    context_info = {'request': request, 'form': form}
    template_path = 'impersonate_user.html'
    if post_data:
        impersonated_user_id = post_data.get('id')
        form_errors = []
        if impersonated_user_id:
            request.session["user_impersonation"] = True
            request.session["user_impersonator"] = serialize_user(request.user)
            try:
                impersonated_user = get_cache_user(impersonated_user_id)
                request.session["user_impersonated"] = serialize_user(impersonated_user)
                return redirect('home')
            except Exception as e:
                logger.error("An error occurred trying to impersonate user.")
                logger.error(str(e))
                form_errors.append("Invalid user for impersonation.")
        else:
            form_errors.append("User is required for impersonation.")
        context_info["form_errors"] = form_errors
        return _render_response(request, context_info, template_path)
    else:
        return _render_response(request, context_info, template_path)


@bypass_impersonation_login_required
def stop_impersonate_user(request):
    if request.session:
        user_impersonation = request.session.get("user_impersonation", False)
        if user_impersonation:
            request.session["user_impersonation"] = False
            request.session["user_impersonated"] = None
            request.session["user_impersonator"] = None
            return redirect('home')
        else:
            logger.error("An error occurred trying to stop impersonating user.")
            logger.error("There is no user being impersonated.")
            pass  # TODO: Return error no user impersonated


@bypass_impersonation_login_required
def erase_log(request):
    try:
        if request.POST:
            log_file_path = os.path.join(settings.PROJECT_ROOT, 'log/sundog.log')
            with open(log_file_path, 'w'):
                pass
            return JsonResponse({'result': 'OK'})
    except Exception as e:
        logger.error("An error occurred trying to delete the log.")
        logger.error(str(e))
        return JsonResponse({'result': 'An error occurred!'})


@bypass_impersonation_login_required
def file_detail(request, file_id):
    my_file = services.get_file_by_id_for_user(file_id, request.user)
    if my_file is None:
        raise Http404()
    else:
        if my_file == "Unavailable":
            context_info = {'request': request, 'user': request.user, 'file_id': file_id}
            template_path = 'file/file_disabled.html'
        else:
            documents = Document.objects.filter(file__file_id=file_id)
            client = Contact.objects.get(client_id=my_file.client.client_id)
            # print
            form_client = ContactForm(instance=client)
            documents_json = []
            if documents:
                documents_json = [
                    {
                        'size': t.document.size,
                        'name': t.document.name,
                        'url': t.document.url,
                        'id': t.pk
                    } for t in documents
                ]
            context_info = {
                'request': request,
                'user': request.user,
                'opts': MyFile._meta,
                'file': my_file,
                'documents': documents_json,
                'form_client': form_client
            }
            template_path = 'file/file.html'
        return _render_response(request, context_info, template_path)


@login_required
def list_contacts(request):
    order_by_list = [
        'type',
        'created_at',
        'company',
        'assigned_to',
        'last_name,first_name',
        'phone_number',
        'email',
        'stage',
        'status'
    ]
    page = int(request.GET.get('page', '1'))
    order_by = request.GET.get('order_by', 'created_at')

    if order_by in order_by_list:
        index = order_by_list.index(order_by)
        order_by_list[index] = '-' + order_by

    sort = {'name': order_by.replace('-', ''), 'class': 'sorting_desc' if order_by.find('-') else 'sorting_asc'}

    if order_by == 'last_name,first_name':
        order_by = ['last_name', 'first_name']
    elif order_by == '-last_name,first_name':
        order_by = ['-last_name', '-first_name']
    else:
        order_by = [order_by]

    contacts = Contact.objects.all().order_by(*order_by)
    paginator = Paginator(contacts, 100)
    page = paginator.page(page)
    lists = [('All Contacts', 'all_contacts')]

    context_info = {
        'sort': sort,
        'order_by_list': order_by_list,
        'request': request,
        'user': request.user,
        'page': page,
        'paginator': paginator,
        'lists': lists,
        'menu_page': 'contacts'
    }
    template_path = 'contact/contact_list.html'
    return _render_response(request, context_info, template_path)


@login_required
def workflows(request):
    if not request.GET or 'type' not in request.GET:
        type = STAGE_TYPE_CHOICES[0][0]
    else:
        type = request.GET['type']
    form_stage = StageForm()
    edit_form_stage = StageForm()
    form_status = StatusForm(type)
    edit_form_status = StatusForm(type)
    stages = Stage.objects.all()
    stage_types = STAGE_TYPE_CHOICES

    context_info = {
        'request': request,
        'user': request.user,
        'form_stage': form_stage,
        'form_status': form_status,
        'edit_form_status': edit_form_status,
        'edit_form_stage': edit_form_stage,
        'stages': stages,
        'stage_types': stage_types,
        'stage_type': type,
        'menu_page': 'contacts'
    }
    template_path = 'contact/workflows.html'
    return _render_response(request, context_info, template_path)


@login_required
def add_stage(request):
    if request.method == 'POST' and request.POST:
        post_data = request.POST.copy()
        post_data.pop('stage_type')
        form = StageForm(post_data)
        if form.is_valid():
            stages = list(Stage.objects.all())
            previous_last_order = len(stages)
            stage = form.save(commit=False)
            stage.order = previous_last_order + 1
            stage.save()
            stage_data = 'Ok'
            response = {'result': stage_data}
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
            response = {'errors': form_errors}
        return JsonResponse(response)


@login_required
def edit_stage(request):
    if request.method == 'POST' and request.POST:
        post_data = request.POST.copy()
        post_data.pop('stage_type')
        stage_id = post_data['stage_id']
        instance = Stage.objects.get(stage_id=stage_id)
        form = StageForm(post_data, instance=instance)
        if form.is_valid():
            form.save()
            status_data = 'Ok'
            response = {'result': status_data}
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
            response = {'errors': form_errors}
        return JsonResponse(response)


@login_required
def add_status(request):
    if request.method == 'POST' and request.POST:
        post_data = request.POST.copy()
        type = post_data.pop('stage_type')[0]
        form = StatusForm(type, post_data)
        if form.is_valid():
            stage_id = request.POST['stage']
            statuses = list(Status.objects.filter(stage__stage_id=stage_id))
            previous_last_order = len(statuses)
            status = form.save(commit=False)
            status.order = previous_last_order + 1
            status.save()
            status_data = 'Ok'
            response = {'result': status_data}
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
            response = {'errors': form_errors}
        return JsonResponse(response)


@login_required
def edit_status(request):
    if request.method == 'POST' and request.POST:
        post_data = request.POST.copy()
        type = post_data.pop('stage_type')[0]
        status_id = request.POST['status_id']
        instance = Status.objects.get(status_id=status_id)
        form = StatusForm(type, post_data, instance=instance)
        if form.is_valid():
            form.save()
            status_data = 'Ok'
            response = {'result': status_data}
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
            response = {'errors': form_errors}
        return JsonResponse(response)


@login_required
def update_stage_order(request):
    if not request.is_ajax():
        redirect('home') # TODO: handle this a generic way perhaps
    response = {'result': None}
    if request.method == 'POST' and request.POST:
        new_order = copy.copy(request.POST)
        new_order.pop('csrfmiddlewaretoken')
        new_order_list = []
        for i in range(0, len(new_order)):
            stage_id_str = new_order[str(i)]
            new_order_list.append(int(stage_id_str))
        reorder_stages(new_order_list)
        response['result'] = 'Ok'
    return JsonResponse(response)


@login_required
def update_status_order(request):
    if not request.is_ajax():
        redirect('home')  # TODO: handle this a generic way perhaps
    response = {'result': None}
    if request.method == 'POST' and request.POST:
        new_order = copy.copy(request.POST)
        new_order.pop('csrfmiddlewaretoken')
        stage_id = new_order.pop('stageId')[0]
        new_order_list = []
        for i in range(0, len(new_order)):
            stage_id_str = new_order[str(i)]
            new_order_list.append(int(stage_id_str))
        reorder_status(new_order_list, stage_id)
        response['result'] = 'Ok'
    return JsonResponse(response)


@login_required
def campaigns(request):
    order_by_list = [
        'active',
        'created_at',
        'created_by',
        'title',
        'source',
        'cost',
        'priority',
        'media_type',
        'purchase_amount'
    ]
    page = int(request.GET.get('page', '1'))
    order_by = request.GET.get('order_by', 'created_at')

    if order_by in order_by_list:
        index = order_by_list.index(order_by)
        order_by_list[index] = '-' + order_by

    sort = {'name': order_by.replace('-', ''), 'class': 'sorting_desc' if order_by.find('-') else 'sorting_asc'}
    order_by = [order_by]

    form_campaign = CampaignForm()
    edit_form_campaign = CampaignForm()
    form_source = SourceForm()
    campaign_list = Campaign.objects.all().order_by(*order_by)
    paginator = Paginator(campaign_list, 100)
    page = paginator.page(page)

    context_info = {
        'request': request,
        'user': request.user,
        'sort': sort,
        'order_by_list': order_by_list,
        'form_source': form_source,
        'form_campaign': form_campaign,
        'edit_form_campaign': edit_form_campaign,
        'paginator': paginator,
        'page': page,
        'menu_page': 'contacts'
    }
    template_path = 'contact/campaigns.html'
    return _render_response(request, context_info, template_path)


@login_required
def add_campaign(request):
    if request.method == 'POST' and request.POST:
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()
            response_data = 'Ok'
            response = {'result': response_data}
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
            response = {'errors': form_errors}
        return JsonResponse(response)


@login_required
def edit_campaign(request):
    if request.method == 'POST' and request.POST:
        campaign_id = request.POST['campaign_id']
        instance = Campaign.objects.get(campaign_id=campaign_id)
        form = CampaignForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            response_data = 'Ok'
            response = {'result': response_data}
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
            response = {'errors': form_errors}
        return JsonResponse(response)


@login_required
def add_source(request):
    if request.method == 'POST' and request.POST:
        form = SourceForm(request.POST)
        if form.is_valid():
            form.save()
            response_data = 'Ok'
            response = {'result': response_data}
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
            response = {'errors': form_errors}
        return JsonResponse(response)


@login_required
def add_contact(request):
    form_errors = None
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and request.POST:
        if form.is_valid():
            form.save()
            return redirect('list_contacts')
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
    context_info = {
        'request': request,
        'user': request.user,
        'form': form,
        'form_errors': form_errors,
        'templates':  [('Add a Client', 'add_a_client')],
        'label': 'Add',
        'menu_page': 'contacts',
    }
    template_path = 'contact/contact.html'
    return _render_response(request, context_info, template_path)


@login_required
def edit_contact(request, contact_id):
    form_errors = None
    instance = Contact.objects.get(contact_id=contact_id)
    form = ContactForm(request.POST or None, instance=instance)
    if request.method == 'POST' and request.POST:
        if form.is_valid():
            form.save()
            return redirect('list_contacts')
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
    context_info = {
        'request': request,
        'user': request.user,
        'form': form,
        'contact_id': contact_id,
        'form_errors': form_errors,
        'templates':  [('Add a Client', 'add_a_client')],
        'label': 'Edit',
        'menu_page': 'contacts'
    }
    template_path = 'contact/contact.html'
    return _render_response(request, context_info, template_path)


@login_required
def get_stage_statuses(request):
    if request.POST and 'stage_id' in request.POST:
        stage_id = request.POST['stage_id']
        statuses = [{'id': status.status_id, 'name': status.name} for status in list(Status.objects.filter(stage__stage_id=stage_id))]
        return JsonResponse({'statuses': statuses})


@login_required
def edit_contact_status(request, contact_id):
    form_errors = None
    instance = Contact.objects.get(contact_id=contact_id)
    form = ContactStatusForm(request.POST or None, instance=instance)
    if request.method == 'POST' and request.POST:
        if form.is_valid():
            form.save()
            return redirect('list_contacts')
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
    context_info = {
        'request': request,
        'user': request.user,
        'contact': instance,
        'form': form,
        'form_errors': form_errors,
        'menu_page': 'contacts'
    }
    template_path = 'contact/edit_contact_status.html'
    return _render_response(request, context_info, template_path)


@login_required
def add_lead_source(request):
    form_errors = None
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and request.POST:
        if form.is_valid():
            lead_source = form.save()
            # TODO: redirect to lead sources list?
            return redirect('home')
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)
    context_info = {
        'request': request,
        'user': request.user,
        'form': form,
        'form_errors': form_errors,
    }
    template_path = 'lead_source/add_lead_source.html'
    return _render_response(request, context_info, template_path)


@permission_required('sundog.change_myfile')
def file_edit(request, file_id):
    error_code = 0
    if 'error_code' in request.session:
        error_code = request.session['error_code']
        request.session.pop('error_code')
    my_file = services.get_file_by_id_for_user(file_id, request.user)
    if my_file is None:
        raise Http404()
    else:
        if my_file == "Unavailable":
            context_info = {'request': request, 'user': request.user, 'file_id': file_id}
            template_path = 'file/file_form.html'
        else:
            form_errors = None
            if request.user.has_perm('sundog.add_client'):
                form_client = ContactForm()
            else:
                form_client = None
            current_status = my_file.current_status
            form = FileCustomForm(instance=my_file)
            form.fields['current_status'].queryset = services.get_status_list_by_user(request.user)

            documents = services.get_file_documents(file_id)
            documents_json = []
            users_json = []
            if documents:
                documents_json = [
                    {
                        'size': t.document.size,
                        'name': t.document.name,
                        'url': t.document.url,
                        'id': t.pk
                    } for t in documents
                ]
            users = services.get_participants_options_by_file(my_file, list(my_file.participants.all()))
            if users:
                users_json = [
                    {'full_name': u.get_full_name() if u.get_full_name() else u.username, 'id': u.pk} for u in users
                ]
            if request.method == 'POST' and request.POST:
                response = None
                form = FileCustomForm(request.POST, instance=my_file)
                form.fields['current_status'].queryset = services.get_status_list_by_user(request.user)
                if form.is_valid():
                    my_file = form.save(commit=False)
                    # TODO: MAKE SURE THE USER HAS CHANGE TAG PERMISSION
                    if current_status.status_id != my_file.current_status.status_id:
                        try:
                            user_impersonator = None
                            if hasattr(request, 'user_impersonator'):
                                user_impersonator = request.user_impersonator
                            file_status_history = FileStatusHistory()
                            file_status_history.create_new_file_status_history(
                                current_status, my_file.current_status, request.user, user_impersonator)
                            my_file.file_status_history.add(file_status_history)
                        except Exception as e:
                            logger.error(messages.ERROR_SAVE_FILE_HISTORY % my_file.file_id)
                            logger.error(e)

                    my_file.stamp_updated_values(request.user)
                    if 'description' in form.changed_data:
                        current_permission = Permission.objects.get(codename=my_file.get_permission_codename())
                        try:
                            current_permission.codename = my_file.get_permission_codename()
                            current_permission.name = my_file.get_permission_name()
                            current_permission.save()
                        except Exception as e:
                            logger.error(messages.ERROR_MODIFY_STATUS_PERMISSION % my_file.name)
                            logger.error(e)
                    actual_file = MyFile.objects.get(file_id=file_id)
                    if actual_file.get_hashcode() == request.POST.get('hashcode') or request.POST.get('override'):
                        form.save_m2m()
                        my_file.save()
                        response = {"noChanges": True}
                    else:
                        response = {"noChanges": False, "changedBy": my_file.last_update_user_username}
                else:
                    form_errors = []
                    for field in form:
                        if field.errors:
                            for field_error in field.errors:
                                form_errors.append(strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error)
                    for non_field_error in form.non_field_errors():
                        form_errors.append(non_field_error)
                    response = {"form_errors": form_errors}
                return HttpResponse(json.dumps(response), content_type="application/json")
            context_info = {
                'request': request, 'user': request.user, 'form': form, 'file_id': file_id, 'opts': MyFile._meta,
                'file': my_file, 'documents': documents_json, 'message': CODES_TO_MESSAGE[error_code],
                'participant_options': users_json, 'form_errors': form_errors, 'form_client': form_client,
            }
            template_path = 'file/file_form.html'
        return _render_response(request, context_info, template_path)


@permission_required('sundog.add_myfile')
def file_add(request):
    form_errors = None
    form = FileCustomForm(request.POST or None)
    form.fields['current_status'].queryset = services.get_status_list_by_user(request.user)
    if request.user.has_perm('sundog.add_client'):
        form_client = ContactForm()
    else:
        form_client = None
    if request.method == 'POST' and request.POST:
        if form.is_valid():
            my_file = form.save(commit=False)
            my_file.stamp_created_values(request.user)
            my_file.save()
            try:
                user_impersonator = None
                if hasattr(request, 'user_impersonator'):
                    user_impersonator = request.user_impersonator
                services.create_file_permission(my_file)
                file_status_history = FileStatusHistory()
                file_status_history.create_new_file_status_history(
                    None, my_file.current_status, request.user, user_impersonator)
                my_file.file_status_history.add(file_status_history)
            except Exception as e:
                logger.error(messages.ERROR_SAVE_FILE_HISTORY % my_file.file_id)
                logger.error(e)

            return redirect('file_detail', file_id=my_file.file_id)
        else:
            form_errors = []
            for field in form:
                if field.errors:
                    for field_error in field.errors:
                        error = strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error
                        form_errors.append(error)
            for non_field_error in form.non_field_errors():
                form_errors.append(non_field_error)

    context_info = {
        'request': request,
        'user': request.user,
        'form': form,
        'form_client': form_client,
        'form_errors': form_errors
    }
    template_path = 'file/file_new.html'
    return _render_response(request, context_info, template_path)


@permission_required('sundog.import_files')
def file_import(request):
    if request.method == 'POST' and request.FILES:
        user_impersonator = None
        if hasattr(request, 'user_impersonator'):
            user_impersonator = request.user_impersonator
        try:
            input_excel = request.FILES['file']
            error = services.upload_import_file(input_excel, request.user, user_impersonator)
        except Exception:
            error = "Error trying to access the import file."
        if error:
            return JsonResponse({'result': error})
        else:
            return JsonResponse({'result': 'OK'})
    context_info = {'request': request, 'user': request.user}
    template_path = 'file/file_import.html'
    return _render_response(request, context_info, template_path)


@permission_required('sundog.import_files')
def check_file_import(request):
    if request.method == 'POST' and request.FILES:
        error = None
        warning = None
        try:
            input_excel = request.FILES['file']
            checksum_file = utils.md5_for_file(input_excel.chunks())
            checksum_exists = services.check_file_history_checksum(checksum_file)
            if checksum_exists:
                warning = "The import file seems to be already uploaded on the server. Do you want to continue?"
        except Exception:
            error = "Error trying to access the file import excel."
        if error:
            return JsonResponse({'error': error})
        else:
            if warning:
                return JsonResponse({'warning': warning})
            else:
                return JsonResponse({'result': 'OK'})
    raise Http404()


@permission_required('sundog.add_client')
def add_client_ajax(request):
    if request.method == 'POST' and request.POST:
        error = None
        new_client = None
        instance = None
        try:
            data = request.POST
            if "client_id" in data:
                instance = Contact.objects.filter(client_id=data["client_id"])
            if instance and len(instance) > 0:
                form_client = ContactForm(data, instance=instance[0])
            else:
                form_client = ContactForm(data)

            if form_client.is_valid():
                new_client = form_client.save()
            else:
                error = []
                for field in form_client:
                    if field.errors:
                        for field_error in field.errors:
                            error.append(strip_tags(field.html_name.replace("_", " ").title()) + ": " + field_error)
                for non_field_error in form_client.non_field_errors():
                    error.append(non_field_error)
        except Exception:
            error = "Error trying to save the new client."
        if error:
            return JsonResponse({'error': error})
        else:
            return JsonResponse({'result': {'client_id': new_client.client_id, 'name': new_client.first_name}})
    raise Http404()


@permission_required('sundog.import_files')
def download_file_import_sample(request):
    path_to_file = os.path.join(settings.PROJECT_ROOT, 'import', 'sample', IMPORT_FILE_EXCEL_FILENAME)
    f = open(path_to_file, 'rb')
    my_file = File(f)
    response = HttpResponse(my_file, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=%s' % IMPORT_FILE_EXCEL_FILENAME
    response['Content-Length'] = os.path.getsize(path_to_file)
    return response


@permission_required('sundog.import_clients')
def client_import(request):
    if request.method == 'POST' and request.FILES:
        try:
            user_impersonator = None
            if hasattr(request, 'user_impersonator'):
                user_impersonator = request.user_impersonator
            input_excel = request.FILES['file']
            error = services.upload_import_client(input_excel, request.user, user_impersonator)
        except Exception as e:
            error = "Error trying to access the import excel file."
        if error:
            return JsonResponse({'result': error})
        else:
            return JsonResponse({'result': 'OK'})

    context_info = {'request': request, 'user': request.user}
    template_path = 'client/client_import.html'
    return _render_response(request, context_info, template_path)


@permission_required('sundog.import_clients')
def check_client_import(request):
    if request.method == 'POST' and request.FILES:
        error = None
        warning = None
        try:
            input_excel = request.FILES['file']
            # warn the user if the file checksum exists
            checksum_file = utils.md5_for_file(input_excel.chunks())
            checksum_exists = services.check_file_history_checksum(checksum_file)
            if checksum_exists:
                warning = "The import excel file seems to be already uploaded on the server. Do you want to continue?"
        except Exception as e:
            error = "Error trying to access the import excel file."
        if error:
            return JsonResponse({'error': error})
        else:
            if warning:
                return JsonResponse({'warning': warning})
            else:
                return JsonResponse({'result': 'OK'})
    raise Http404()


@permission_required('sundog.import_clients')
def download_client_import_sample(request):
    path_to_file = os.path.join(settings.PROJECT_ROOT, 'import', 'sample', IMPORT_CLIENT_EXCEL_FILENAME)
    f = open(path_to_file, 'rb')
    my_file = File(f)
    response = HttpResponse(my_file, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=%s' % IMPORT_CLIENT_EXCEL_FILENAME
    response['Content-Length'] = os.path.getsize(path_to_file)
    return response


@permission_required('sundog.change_file')
def documents_upload(request, file_id):
    if request.method == 'POST' and request.FILES:
        my_file = services.get_file_by_id_for_user(file_id, request.user)
        if my_file:
            document = Document(document=request.FILES['file'], file=my_file)
            document.save()
            return JsonResponse({'document_id': document.pk})
    raise Http404()


@permission_required('sundog.change_file_participant')
def file_remove_participant(request, file_id):
    my_file = services.get_file_by_id_for_user(file_id, request.user)
    error_code = MESSAGE_REQUEST_FAILED_CODE
    if request.method == 'POST' and request.POST and file_id:
        if request.POST["user_id"]:
            user_id = request.POST["user_id"]
            user = get_cache_user(user_id)
            if my_file and user:
                my_file.participants.remove(user)
                my_file.save()
                return redirect('file_edit', file_id=file_id)
    request.session['error_code'] = error_code
    return redirect('file_edit', file_id=file_id)


@permission_required('sundog.change_file_participant')
def file_add_participant(request, file_id):
    my_file = services.get_file_by_id_for_user(file_id, request.user)
    error_code = MESSAGE_REQUEST_FAILED_CODE
    if my_file and request.method == 'POST' and request.POST:
        if request.POST.getlist('new_participants'):
            new_participants = request.POST.getlist('new_participants')
            users = list(services.get_users_by_ids(new_participants))
            my_file.participants.add(*users)
            my_file.save()
            return redirect('file_edit', file_id=file_id)
    request.session['error_code'] = error_code
    return redirect('file_edit', file_id=file_id)


@permission_required('sundog.change_file')
def documents_delete(request, document_id):
    if request.method == 'POST' and document_id:
        db_doc = Document.objects.get(pk=document_id)
        if os.path.isfile(db_doc.document.path):
            os.remove(db_doc.document.path)
        db_doc.delete()
        return JsonResponse({'result': 'OK'})
    raise Http404()


@bypass_impersonation_login_required
def messages_upload(request, file_id):
    if request.method == 'POST' and request.POST:
        my_file = services.get_file_by_id_for_user(file_id, request.user)
        if my_file:
            message = Message(message=request.POST['message'])
            message.time = datetime.now()
            message.user = request.user
            message.save()
            my_file.messages.add(message)
            my_file.save()
            # change to localtime
            message_time = utils.set_date_to_user_timezone(message.time, request.user.id)
            user = get_cache_user(message.user.id)
            user_full_name = user.get_full_name() if user.get_full_name() != '' else user.username
            return JsonResponse({
                'message': {
                    'time': utils.format_date(message_time),
                    'user_full_name': user_full_name
                },
                'count': my_file.messages.count()
            })
    raise Http404()


class FileSearchView(SearchView):
    form_class = FileSearchForm
    template_name = 'home.html'

    def get(self, request, *args, **kwargs):
        request.GET = request.GET.copy()
        created_end = request.GET.get('created_end')
        created_start = request.GET.get('created_start')
        if created_start == '01/01/1970':
            request.GET['created_start'] = ''
        if (created_end and created_start == '') or (created_end == '' and created_start):
            if created_end and created_start == '':
                request.GET['created_start'] = '01/01/1970'
            if created_end == '' and created_start:
                request.GET['created_end'] = datetime.now().strftime("%m/%d/%Y")
        return super(FileSearchView, self).get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super(FileSearchView, self).get_queryset()
        participants = False
        try:
            radio_field = self.request.GET['radio_field']
            if radio_field == '1':
                participants = True
        except:
            pass
        if not self.request.user.is_superuser:
            # filter file for status permission
            permissions_name_array = services.get_user_status_permissions(self.request.user)

            # filter permission to view all files or only files where the user is participant
            if not self.request.user.has_perm('sundog.view_all_files') or participants:
                queryset = queryset.filter(status__in=permissions_name_array,
                                           participants=self.request.user.id)
            else:
                queryset = queryset.filter(status__in=permissions_name_array)
        else:
            if participants:
                queryset = queryset.filter(participants=self.request.user.id)
        return queryset

    def get_context_data(self, *args, **kwargs):
        context = super(FileSearchView, self).get_context_data(*args, **kwargs)
        # do something
        status_result = services.get_files_by_status_count(self.request.user)
        status_results_json = []
        status_names = []
        date_row = None
        dict_row = None
        for row in status_result:
            if not row.file_status.title() in status_names:
                status_names.append(row.file_status.title())
            if not date_row:
                dict_row = {'day': str(row.date_stat)}
                date_row = row.date_stat

            if date_row == row.date_stat:
                dict_row[row.file_status.title()] = row.file_count
            else:
                status_results_json.append(dict_row)
                date_row = None
        if dict_row:
            status_results_json.append(dict_row)
        context['chart_data'] = status_results_json
        context['chart_status_names'] = status_names
        return context

    def get_form(self, form_class=None):
        form = super(FileSearchView, self).get_form(form_class)
        form.fields['status'].queryset = services.get_status_list_by_user(self.request.user)
        return form
