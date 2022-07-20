// logging key-value pairs of FormData object
function logFormData(data) {
    for (const pair of data.entries()) {
        console.log(pair[0] + ": " + pair[1]);
    }
}


// fade out message alerts
function fade_alerts() {
    alerts = document.getElementsByClassName("alert msg");
    var i = alerts.length;
    for (let elem of alerts) {
        i--;
        time = 3250 + (1000 * i);
        setTimeout(function () {
            $(elem).fadeOut("slow");
        }, time);
    }
}

// call fade out after DOMContentLoaded
window.addEventListener('DOMContentLoaded', (event) => {
    fade_alerts();
});

document.body.addEventListener('click', function (event) {
    if (event.target.className === 'unique_class_name') {
        const form = event.target.form;
        const data = new FormData(form);

        const request = new XMLHttpRequest();
        request.open(form.method, form.action, true);
        request.send(data);

        // logFormData(data);

        request.addEventListener("load", function () {
            if (this.readyState === 4 && this.status === 200) {

                // catch JsonResponse from Django
                const response = JSON.parse(this.responseText);

                // display message
                const messages = document.getElementById("messages-list");
                messages.innerHTML += response.msg;
                fade_alerts();
            }
        });
    }

});