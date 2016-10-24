from django import forms
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django_auth_app import enums
from sundog.models import (
    BankAccount,
    Call,
    Campaign,
    Contact,
    Creditor,
    Debt,
    DebtNote,
    DEBT_SETTLEMENT,
    Email,
    EnrollmentPlan,
    Expenses,
    Fee,
    FeeProfile,
    FeeProfileRule,
    Incomes,
    Note,
    Source,
    Stage,
    Status,
    Uploaded,
    WorkflowSettings,
)
from sundog import services
from sundog.constants import SHORT_DATE_FORMAT
from sundog.utils import hash_password


class ImpersonateUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['id']

    id = forms.ModelChoiceField(
        required=True, widget=forms.Select(attrs={'class': 'form-control'}), queryset=[])

    def __init__(self, id, *args, **kwargs):
        super(ImpersonateUserForm, self).__init__(*args, **kwargs)
        self.fields['id'].queryset = services.get_impersonable_users(id)


EMPTY_LABEL = '--Select--'


class ContactForm(forms.ModelForm):

    class Meta:
        widgets = {
            'contact_id': forms.HiddenInput(),
        }
        model = Contact
        exclude = ['last_status_change', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super(ContactForm, self).__init__(*args, **kwargs)
        self.fields['assigned_to'].empty_label = EMPTY_LABEL
        self.fields['lead_source'].empty_label = EMPTY_LABEL
        self.fields['company'].empty_label = EMPTY_LABEL
        self.fields['stage'].empty_label = EMPTY_LABEL
        self.fields['status'].empty_label = EMPTY_LABEL
        self.fields['call_center_representative'].empty_label = EMPTY_LABEL

    def clean(self):
        if 'contact_id' in self.data:
            contact_id = int(self.data['contact_id'])
            self.cleaned_data['contact_id'] = contact_id


class ContactStatusForm(forms.ModelForm):

    class Meta:
        model = Contact
        fields = ['contact_id', 'stage', 'status']
        widgets = {
            'contact_id': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super(ContactStatusForm, self).__init__(*args, **kwargs)
        self.fields['status'].empty_label = EMPTY_LABEL
        self.fields['stage'].empty_label = EMPTY_LABEL
        self.fields['status'].required = True

        if args == (None,) and 'instance' in kwargs and kwargs['instance']:
            instance = kwargs['instance']
            self.fields['status'].queryset = Status.objects.filter(stage=instance.stage)
        elif args and args[0] and 'stage' in args[0]:
            stage_id = args[0]['stage']
            self.fields['status'].queryset = Status.objects.filter(stage__stage_id=stage_id)
        else:
            self.fields['status'].queryset = Status.objects.none()


class StageForm(forms.ModelForm):

    class Meta:
        model = Stage
        fields = ['name', 'stage_id', 'type']
        widgets = {
            'stage_id': forms.HiddenInput(),
            'type': forms.HiddenInput(),
        }


class StatusForm(forms.ModelForm):

    class Meta:
        model = Status
        fields = ['name', 'stage', 'color', 'status_id']
        widgets = {
            'status_id': forms.HiddenInput(),
        }

    def __init__(self, type=DEBT_SETTLEMENT, *args, **kwargs):
        super(StatusForm, self).__init__(*args, **kwargs)
        self.fields['stage'].queryset = self.fields['stage'].queryset.filter(type=type)
        self.fields['stage'].empty_label = EMPTY_LABEL


class WorkflowSettingsForm(forms.ModelForm):
    class Meta:
        model = WorkflowSettings
        fields = '__all__'
        widgets = {
            'on_submission': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_returned': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_reject': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_approval': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_second_approval': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_enrollment': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_de_enroll': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_re_enroll': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_graduation': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_un_graduate': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_dropped': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_contract_upload': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_first_payment_processed': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_first_payment_cleared': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_first_payment_return': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_final_payment': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'require_plan': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_bank': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_credit_card': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_bank_or_cc': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_debts': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_submit': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_contract_to_submit': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_contract_to_enroll': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'allow_reject': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_approval': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_secondary_approval': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_inc_exp': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'enforce_required_fields': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'require_comp_template': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'pause_on_nsf': forms.CheckboxInput(attrs={'class': 'col-xs-3 no-padding-sides'}),
            'on_pause': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_resume': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
            'on_returned_payment': forms.Select(attrs={'class': 'col-xs-6 no-padding-sides'}),
        }


class CampaignForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(CampaignForm, self).__init__(*args, **kwargs)
        self.fields['source'].empty_label = EMPTY_LABEL

    class Meta:
        model = Campaign
        exclude = ['created_by', 'created_at', 'updated_at']
        widgets = {
            'campaign_id': forms.HiddenInput(),
            'start_date': forms.DateInput(
                format=SHORT_DATE_FORMAT,
                attrs={
                    'placeholder': 'mm/dd/yyyy',
                    'data-provide': 'datepicker',
                }
            ),
            'end_date': forms.DateInput(
                format=SHORT_DATE_FORMAT,
                attrs={
                    'placeholder': 'mm/dd/yyyy',
                    'data-provide': 'datepicker',
                }
            ),
        }


class SourceForm(forms.ModelForm):

    class Meta:
        model = Source
        fields = ['name']


class BankAccountForm(forms.ModelForm):

    class Meta:
        model = BankAccount
        widgets = {
            'contact': forms.HiddenInput(),
        }
        exclude = ['created_at', 'updated_at', 'account_number_salt', 'account_number_last_4_digits']

    def __init__(self, *args, **kwargs):
        super(BankAccountForm, self).__init__(*args, **kwargs)
        self.previous_account_number = kwargs.get('instance').account_number if kwargs.get('instance') else None
        if kwargs and 'instance' in kwargs and not args:
            bank_account = kwargs['instance']
            if bank_account and bank_account.account_number_last_4_digits:
                self.initial['account_number'] = '******' + bank_account.account_number_last_4_digits

    def save(self, commit=True):
        account_number_changed = True
        if self.instance:
            if self.cleaned_data and 'account_number' in self.cleaned_data:
                account_number = self.cleaned_data['account_number']
                if account_number == '******' + self.instance.account_number_last_4_digits:
                    account_number_changed = False
                    self.cleaned_data['account_number'] = self.previous_account_number
                    self.instance.account_number = self.previous_account_number
        if account_number_changed:
            hash_password(self.instance)
        return super(BankAccountForm, self).save(commit=commit)


class NoteForm(forms.ModelForm):

    class Meta:
        model = Note
        widgets = {
            'contact': forms.HiddenInput(),
            'created_by': forms.HiddenInput(),
            'description': forms.Textarea(attrs={'class': 'col-xs-12 no-padding', 'rows': 6}),
            'type': forms.Select(attrs={'class': 'col-xs-12 no-padding'}),
            'cc': forms.TextInput(attrs={'class': 'col-xs-12 no-padding'})
        }
        exclude = ['created_at']

    def __init__(self, contact, user, *args, **kwargs):
        super(NoteForm, self).__init__(*args, **kwargs)
        self.fields['contact'].initial = contact
        self.fields['created_by'].initial = user


class CallForm(forms.ModelForm):
    minutes = forms.CharField(widget=forms.TextInput(attrs={'type': 'number', 'style': 'width: 70px;'}))
    seconds = forms.CharField(widget=forms.TextInput(attrs={'type': 'number', 'style': 'width: 70px;'}))
    contact_status = forms.ModelChoiceField(queryset=Status.objects.none())

    class Meta:
        model = Call
        widgets = {
            'contact': forms.HiddenInput(),
            'created_by': forms.HiddenInput(),
            'description': forms.Textarea(attrs={'class': 'col-xs-12 no-padding', 'rows': 6})
        }
        exclude = ['created_at']

    def __init__(self, contact, user, *args, **kwargs):
        super(CallForm, self).__init__(*args, **kwargs)
        self.fields['contact'].initial = contact
        self.fields['created_by'].initial = user
        self.fields['type'].initial = 'outgoing'
        self.fields['type'].empty_label = None
        self.fields['contact_status'].empty_label = None
        if contact.stage:
            self.fields['contact_status'].queryset = Status.objects.filter(stage=contact.stage)
        if contact.status:
            self.fields['contact_status'].initial = contact.status

    def save(self, commit=True):
        minutes = self.cleaned_data.pop('minutes')
        seconds = self.cleaned_data.pop('seconds')
        self.cleaned_data['duration'] = (minutes + ':' if minutes else '') + \
                                        ('0' if not seconds and minutes else seconds)
        return super(CallForm, self).save(commit=commit)


class MultiEmailField(forms.Field):
    def to_python(self, value):
        if not value:
            return []
        return value.split(',')

    def validate(self, value):
        super(MultiEmailField, self).validate(value)
        for email in value:
            validate_email(email)


class EmailForm(forms.ModelForm):
    file_upload = forms.FileField(required=False)
    emails_to = MultiEmailField(widget=forms.TextInput(attrs={'class': 'col-xs-12 no-padding'}))
    cc = MultiEmailField(required=False, widget=forms.TextInput(attrs={'class': 'col-xs-12 no-padding'}))

    class Meta:
        model = Email
        widgets = {
            'contact': forms.HiddenInput(),
            'email_from': forms.EmailInput(attrs={'class': 'col-xs-6 no-padding'}),
            'message': forms.Textarea(attrs={'class': 'col-xs-12 no-padding', 'id': 'message'}),
            'subject': forms.TextInput(attrs={'class': 'col-xs-12 no-padding'}),
        }
        exclude = ['created_at']

    def __init__(self, contact, user, *args, **kwargs):
        super(EmailForm, self).__init__(*args, **kwargs)
        self.fields['contact'].initial = contact
        self.fields['created_by'].initial = user

    def clean_emails_to(self):
        data = self.cleaned_data['emails_to']
        data = ','.join(data)
        return data


class UploadedForm(forms.ModelForm):
    class Meta:
        model = Uploaded
        widgets = {
            'contact': forms.HiddenInput(),
            'created_by': forms.HiddenInput(),
            'name': forms.HiddenInput(),
            'mime_type': forms.HiddenInput(),
            'description': forms.Textarea(attrs={'class': 'col-xs-12 no-padding',
                                                 'style': 'max-width: 566px;min-height: 200px'}),
            'content': forms.FileInput(attrs={'style': 'padding-left: 3px;'}),
        }
        exclude = ['created_at']

    def __init__(self, contact, user, *args, **kwargs):
        super(UploadedForm, self).__init__(*args, **kwargs)
        self.fields['contact'].initial = contact
        self.fields['created_by'].initial = user


class IncomesForm(forms.ModelForm):
    class Meta:
        model = Incomes
        widgets = {
            'contact': forms.HiddenInput(),
        }
        fields = '__all__'

    def __init__(self, contact, *args, **kwargs):
        super(IncomesForm, self).__init__(*args, **kwargs)
        self.fields['contact'].initial = contact


class ExpensesForm(forms.ModelForm):
    class Meta:
        model = Expenses
        widgets = {
            'contact': forms.HiddenInput(),
        }
        fields = '__all__'

    def __init__(self, contact, *args, **kwargs):
        super(ExpensesForm, self).__init__(*args, **kwargs)
        self.fields['contact'].initial = contact


class CreditorForm(forms.ModelForm):
    class Meta:
        model = Creditor
        widgets = {
            'creditor_id': forms.HiddenInput(),
        }
        fields = '__all__'


DATE_INPUT_SETTINGS = {
    'format': SHORT_DATE_FORMAT,
    'attrs': {'placeholder': 'mm/dd/yyyy', 'data-provide': 'datepicker', 'data-date-autoclose': 'true'},
}


class DebtForm(forms.ModelForm):
    note = forms.CharField(required=False, widget=forms.Textarea(
        attrs={'style': 'resize: none;', 'class': 'form-control', 'maxlength': 2000}))

    class Meta:
        model = Debt
        widgets = {
            'debt_id': forms.HiddenInput(),
            'contact': forms.HiddenInput(),
            'last_payment_date': forms.DateInput(**DATE_INPUT_SETTINGS),
            'summons_date': forms.DateInput(**DATE_INPUT_SETTINGS),
            'court_date': forms.DateInput(**DATE_INPUT_SETTINGS),
            'discovery_date': forms.DateInput(**DATE_INPUT_SETTINGS),
            'answer_date': forms.DateInput(**DATE_INPUT_SETTINGS),
            'service_date': forms.DateInput(**DATE_INPUT_SETTINGS),
            'paperwork_received_date': forms.DateInput(**DATE_INPUT_SETTINGS),
            'poa_sent_date': forms.DateInput(**DATE_INPUT_SETTINGS),
        }
        fields = '__all__'

    def __init__(self, contact, *args, **kwargs):
        super(DebtForm, self).__init__(*args, **kwargs)
        self.fields['contact'].initial = contact


class DebtNoteForm(forms.ModelForm):
    class Meta:
        model = DebtNote
        widgets = {
            'debt_id': forms.HiddenInput(),
            'debt': forms.HiddenInput(),
            'content': forms.Textarea(attrs={'class': 'col-xs-12 no-padding', 'style': 'resize: none;', 'maxlength': 2000}),
        }
        fields = '__all__'


class EnrollmentPlanForm(forms.ModelForm):
    class Meta:
        model = EnrollmentPlan
        widgets = {
            'enrollment_plan_id': forms.HiddenInput(),
            'active': forms.CheckboxInput(),
            'two_monthly_drafts': forms.CheckboxInput(),
            'select_first_payment_date': forms.CheckboxInput(),
            'performance_plan': forms.CheckboxInput(),
            'draft_fee_separate': forms.CheckboxInput(),
            'includes_veritas_legal': forms.CheckboxInput(),
            'legal_plan_flag': forms.CheckboxInput(),
            'debt_amount_flag': forms.CheckboxInput(),
            'debt_to_income_flag': forms.CheckboxInput(),
            'states_flag': forms.CheckboxInput(),
            'show_fee_subtotal_column': forms.CheckboxInput(),
            'savings_adjustment': forms.CheckboxInput(),
            'show_savings_accumulation': forms.CheckboxInput(),
            'states': forms.SelectMultiple(choices=enums.US_STATES, attrs={'class': 'col-xs-2 no-padding-sides', 'style': 'height: 200px;'}),
            'fee_profile': forms.Select(attrs={'class': 'col-xs-2 no-padding-sides'})
        }
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        if kwargs and 'instance' in kwargs and  kwargs['instance'].states:
            kwargs['instance'].states = kwargs['instance'].states.replace('\'', '').replace('[', '').replace(']', '').split(', ')
        super(EnrollmentPlanForm, self).__init__(*args, **kwargs)


class FeeForm(forms.ModelForm):
    enrollment_plan = forms.ModelChoiceField(
        required=False,
        queryset=EnrollmentPlan.objects.all(),
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Fee
        widgets = {
            'fee_id': forms.HiddenInput(),
            'name': forms.TextInput(attrs={'style': 'max-width: 140px;'})
        }
        fields = '__all__'


class FeeProfileForm(forms.ModelForm):
    class Meta:
        model = FeeProfile
        widgets = {}
        fields = '__all__'


class FeeProfileRuleForm(forms.ModelForm):
    class Meta:
        model = FeeProfileRule
        widgets = {}
        fields = '__all__'
