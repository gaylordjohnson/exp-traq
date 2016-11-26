function showDateField() {
  document.getElementById('dateDefault').style.display = 'none';
  
  var dateField = document.getElementById('dateField');
  dateField.style.display = 'block';
  dateField.click();
  dateField.focus();
}

function showCommentField() {
  document.getElementById('commentDefault').style.display = 'none';
  
  var commentField = document.getElementById('commentField');
  commentField.style.display = 'block';
  commentField.focus();
}

function showChangeTraq() {
  document.getElementById('expTraqDefaultView').style.display = 'none';
  document.getElementById('expTraqChangeBtn').style.display = 'none';
  
  var form = document.getElementById('changeTraqForm');
  form.style.display = 'block';
  form.focus();
}

function deleteEntry(item_id) {
  var okToDelete = confirm("OK to delete entry?");
  if (okToDelete == true) {
    var ajaxRequest = new XMLHttpRequest();
    ajaxRequest.onreadystatechange = function() {
      if (ajaxRequest.readyState == 4 && ajaxRequest.status == 200) {
        // Delete the <tr> identified by item_id
        var child = document.getElementById(item_id);
        child.parentNode.removeChild(child);
      }
    };
    ajaxRequest.open('DELETE', 'entry/' + item_id);
    ajaxRequest.send(null);
  }
}

function reloadAsTable() {
  window.location = "/?exp_traq_name={{ exp_traq_name }}&showAs=table";
}
function reloadAsList() {
  window.location = "/?exp_traq_name={{ exp_traq_name }}";
}
