function removeSpinner() {
    $(".spinner-border").remove()
    let content = document.getElementById('content');
    content.classList.remove("invisible")
}

// AJAX function modeled after django-ajax-tables
// https://pypi.org/project/django-ajax-tables/
function displayProfileReturns(querystring = '', url = "{% url 'profile-returns' profile.user.username %}") {
    var xhr = new XMLHttpRequest();
    xhr.onreadystatechange = function() {
        if (xhr.readyState == XMLHttpRequest.DONE ) {
            if (xhr.status == 200) {
                var div = document.getElementById('profile-returns-id');
                div.innerHTML = xhr.responseText;
            }
            removeSpinner()
        }
    };
    xhr.open('GET', url + querystring, true);
    xhr.send();
}

// AJAX function modeled after django-ajax-tables
// https://pypi.org/project/django-ajax-tables/
function displayPortfolioGraph(querystring = '', url = "{% url 'returns-graph' %}") {
    var xhr = new XMLHttpRequest();
    xhr.onreadystatechange = function() {
        if (xhr.readyState == XMLHttpRequest.DONE ) {
            if (xhr.status == 200) {
                Plotly.newPlot("returns-graph-id", JSON.parse(xhr.responseText));
            }
            removeSpinner()
        }
    };
    xhr.open('GET', url + querystring, true);
    xhr.send();
}
