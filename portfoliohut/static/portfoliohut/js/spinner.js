window.onload = function() {
    $(".spinner-border").fadeOut()
    let content = document.getElementById('content');
    content.classList.remove("invisible")
    let row = document.querySelectorAll('[data-username="{{request.user.username}}"]')[0];
    row.classList.add("bg-light");
  };
