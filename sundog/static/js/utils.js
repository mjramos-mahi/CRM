function showErrorToast(message){
    toastr.options = {
        "closeButton": true,
        "debug": false,
        "newestOnTop": false,
        "progressBar": true,
        "positionClass": "toast-bottom-center",
        "preventDuplicates": false,
        "onclick": null,
        "showDuration": "300",
        "hideDuration": "1000",
        "timeOut": "5000",
        "extendedTimeOut": "1000",
        "showEasing": "swing",
        "hideEasing": "linear",
        "showMethod": "fadeIn",
        "hideMethod": "fadeOut"
    };

    toastr["error"](message)
}

function showSuccessToast(message) {
    toastr.options = {
        "closeButton": true,
        "debug": false,
        "newestOnTop": false,
        "progressBar": true,
        "positionClass": "toast-bottom-center",
        "preventDuplicates": false,
        "onclick": null,
        "showDuration": "300",
        "hideDuration": "1000",
        "timeOut": "1500",
        "extendedTimeOut": "1000",
        "showEasing": "swing",
        "hideEasing": "linear",
        "showMethod": "fadeIn",
        "hideMethod": "fadeOut"
    };

    toastr["success"](message)
}

function showErrorPopup(error){
    if (error != null) {
        if (typeof error == "string") {
            swal("Error!", error, "error");
        } else {
            var errors = error;
            var errorText = "<div align='left' class='sweet-alert-body-scroll'>";
            for(var i=0; i<errors.length; i++){
                errorText += "<strong>&#187;</strong> " + errors[i] + "<br/>";
            }
            errorText += "</div>";
            swal({
                title: "Validation Error(s)",
                html: true,
                type: "error",
                text: errorText
            });
        }
    }
}

function showConfirmationPopup(confirmMsg, confirmButtonText, callback, closeOnConfirm) {
    swal(
        {
            title: "Are you sure?",
            html: true,
            showCancelButton: true,
            confirmButtonText: confirmButtonText,
            confirmButtonColor: '#DD6B55',
            closeOnConfirm: closeOnConfirm,
            type: "warning",
            text: confirmMsg
        },
        callback
    );
}

function showConfirmationDeletePopup(confirmMsg, callback, closeOnConfirm) {
    showConfirmationPopup(confirmMsg, 'Yes delete it!', callback, closeOnConfirm);
}

function showSuccessPopup(msg) {
    swal({
        title: "Success",
        html: true,
        type: "success",
        text: msg
    });
}

function resetForm($form) {
    $form.find('input:text, input:password, input:file, select, textarea').val('');
    $form.find('input:radio, input:checkbox').removeAttr('checked').removeAttr('selected');
    $form.find('.chosen-select').find('option:first-child').prop('selected', true).end().trigger('chosen:updated');
}

function redirect(location) {
    window.location.replace(location);
}

function refreshScreen() {
    redirect(window.location);
}


function tinymce_setup(editor) {
    editor.on(
        'change',
        function () {
            editor.save();
        }
    );
}

function handleErrors(response) {
    if (response.errors) {
        showErrorPopup(response.errors);
    }
}

function selectASingleRadioButton(groupSelector, elem) {
    $(groupSelector).prop('checked', false);
    $(elem).prop('checked', true);
}