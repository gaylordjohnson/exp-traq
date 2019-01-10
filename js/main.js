// Let's play with state management:
// Now that we have 3 query string params, it's pain in the butt 
// to manage all the permutations, so will use this global
// state object as a centralized source of truth.

// NOTE: following VSCode's suggestion to use ES2015 classes 
// (https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Classes)
class State {
  constructor() {
    this.traq = null;
    this.showTopN = true;
    this.showAsTable = false;
  }
  // Exp traq name must be passed in, because it comes from the server via jinja2 
  // template and main.js doesn't have access to that.
  // The other parts of the state come from the query string
  initFromServerAndQueryString(expTraqName) {
    this.traq = expTraqName;
    var urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('show')) {
      if (urlParams.get('show') == 'all')
        this.showTopN = false;
      else
        this.showTopN = true;
    }
    if (urlParams.has('showAs')) {
      if (urlParams.get('showAs') == 'table') 
        this.showAsTable = true;
      else
        this.showAsTable = false;
    }
  }
  reloadAsTable() {
    let loc = '/?exp_traq_name=' + this.traq;
    if (!this.showTopN)
      loc += '&show=all';
    loc += '&showAs=table';
    window.location = loc;
  }
  reloadAsList() {
    let loc = '/?exp_traq_name=' + this.traq;
    if (!this.showTopN)
      loc += '&show=all';
    loc += '&showAs=list';
    window.location = loc;
  }
  reloadShowAll() {
    let loc = '/?exp_traq_name=' + this.traq;
    loc += '&show=all';
    if (this.showAsTable)
      loc += '&showAs=table';
    else
      loc += '&showAs=list';
    window.location = loc;
  }
  reloadShowTopN() {
    let loc = '/?exp_traq_name=' + this.traq;
    if (this.showAsTable)
      loc += '&showAs=table';
    else
      loc += '&showAs=list';
    window.location = loc;    
  }
}

// Global state
var state = new State();

/* 
 * Stuff related to the payee autocomplete dropdowns 
 */
function inputChanged(context, payeeDropdownId) {
  var val = context.value.toLowerCase();
  var dropdown = document.getElementById(payeeDropdownId);
  if(val === '') {
    dropdown.style.display = 'none';
    return;
  }
  for (var i = 0; i < dropdown.children.length; i++) {
    var item = dropdown.children[i];
    if(item.innerHTML.toLowerCase().indexOf(val) >= 0) {
      item.style.display = 'block';
      dropdown.style.display = 'block';
    } else {
      item.style.display = 'none';
    }   
  }
}
  
function dropdownItemSelected(context, payeeFieldId, payeeDropdownId) {
  var val = context.innerHTML;
  document.getElementById(payeeFieldId).value = val;
  document.getElementById(payeeDropdownId).style.display = 'none';
}
/* ------------------------------------------ */

function showDateField() {
  document.getElementById('dateDefault').style.display = 'none';
  document.getElementById('dateField').style.display = 'flex';
  document.getElementById('dateInput').focus();
}

function showCommentField() {
  document.getElementById('commentDefault').style.display = 'none';
  document.getElementById('commentField').style.display = 'flex';
  document.getElementById('commentInput').focus();
}

function showChangeTraq() {
  document.getElementById('expTraqDefaultView').style.display = 'none';
  document.getElementById('expTraqChangeBtn').style.display = 'none';
  
  var form = document.getElementById('changeTraqForm');
  form.style.display = 'block';
  document.getElementById('changeExpTraqField').focus();
}

var entryBeingEdited = null; // Entry currently being edited

// Called when user clicks Edit on an entry
function editEntry(id) {
  if (entryBeingEdited)
    entryBeingEdited.style.display = 'block'; // Un-hide entry previously being edited
  entryBeingEdited = document.getElementById(id);
  form = document.getElementById('editForm');

  // Using some jQuery here, since I have jQuery included anyway (required by Bootstrap)
  const amount = $('#' + id).find('.amount').text();
  const payee = $('#' + id).find('.payee').text();
  const date = $('#' + id).find('.dateYMD').text();
  const comment = $('#' + id).find('.comment').text();
  console.log('Editing: [' + date + '] [' + amount + '] [' + payee + '] [' + comment + ']');

  // Assign amount etc. as values inside the form
  $(form).find("[name='amount']").attr('value', amount);
  $(form).find("[name='payee']").attr('value', payee);
  $(form).find("[name='date']").attr('value', date);
  $(form).find("[name='comment']").val(comment);

  entryBeingEdited.parentNode.insertBefore(form, entryBeingEdited);
  entryBeingEdited.style.display = 'none';
  form.style.display = 'block';

  //xx DOESN'T WORK :-(
  // I debugged it and what happens is it gets scrolled into view but then
  // something causes the page to instantly scroll to the top again.
  // Can't figure out what it is...
  form.scrollIntoView({behavior: "smooth", block: "end", inline: "nearest"});
}

// Once page loads, add 'submit' event listener to the editForm.
// (If page not loaded, there's nothing to add listener to.)
// Listener is called when user clicks Save on the entry's edit form.
window.addEventListener('load', function() {
  // Check for presence of form because in our **table** view we have no form
  if (document.getElementById('editForm')) document.getElementById('editForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevents form submission; but field validation still takes place

    var ajaxRequest = new XMLHttpRequest();

    // Handle successful completion of the AJAX call
    // This is async and will be called sometime after this current scope exits
    ajaxRequest.onreadystatechange = function() {
      if (ajaxRequest.readyState == 4 && ajaxRequest.status == 200) {
        console.log('Edit request completed successfully; reloading page');
        window.location.reload() //xx Not sure if I need to reload here, or from python
      }
    };

    var form = document.getElementById('editForm');
    var formData = new FormData(form); // Get field values from form when form was submitted
    const amount = formData.get('amount');
    const payee = formData.get('payee');
    const date = formData.get('date');
    const comment = formData.get('comment');
    console.log('Will PUT [' + date + '] [' + amount + '] [' + payee + '] [' + comment + ']');

    ajaxRequest.open('PUT', 'entry/' + entryBeingEdited.id);
    // From my debugging, seems like webapp2 expects form parameters as application/x-www-form-urlencoded
    ajaxRequest.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    var contentBody = "";
    contentBody += 'amount=' + encodeURIComponent(amount) + '&';
    contentBody += 'payee=' + encodeURIComponent(payee) + '&';
    contentBody += 'date=' + encodeURIComponent(date) + '&';
    contentBody += 'comment=' + encodeURIComponent(comment);
    ajaxRequest.send(contentBody); 
  
    // Close form; show entry: this is same as if user clicked Cancel
    closeEditForm();

    // Not sure this is needed. Seems to work w/o it as well but 
    // some on Stackoverflow say need to return false to prevent default behavior
    return false; 
  });
});

// Used in two places: when clicking Cancel, and at the end of Edit
function closeEditForm() {
  form = document.getElementById('editForm');
  form.style.display = 'none';
  entryBeingEdited.style.display = 'block';
  entryBeingEdited.scrollIntoView(); //xx DOESN'T WORK
}

function deleteEntry(id) {
  var okToDelete = confirm("OK to delete entry?");
  if (okToDelete == true) {
    var ajaxRequest = new XMLHttpRequest();
    ajaxRequest.onreadystatechange = function() {
      if (ajaxRequest.readyState == 4 && ajaxRequest.status == 200) {
        // REPLACING the below with a simple page reload, because
        // this code was insufficient, i.e. it didn't take care of updating
        // entry count...
        //
        // console.log('Delete request completed; deleting entry from DOM');
        // var child = document.getElementById(id);
        // child.parentNode.removeChild(child);
        window.location.reload();
      }
    };
    ajaxRequest.open('DELETE', 'entry/' + id);
    ajaxRequest.send(null);
  }
}
