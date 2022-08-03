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
    this.payeeToFilter = "";
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
    if (urlParams.has('payee')) {
      this.payeeToFilter = urlParams.get('payee');
    }
  }
  reloadAsTable() {
    let loc = '/?exp_traq_name=' + this.traq;
    if (!this.showTopN)
      loc += '&show=all';
    loc += '&showAs=table';
    if (this.payeeToFilter)
      loc += '&payee=' + this.payeeToFilter;
    window.location = loc;
  }
  reloadAsList() {
    let loc = '/?exp_traq_name=' + this.traq;
    if (!this.showTopN)
      loc += '&show=all';
    loc += '&showAs=list';
    if (this.payeeToFilter)
      loc += '&payee=' + this.payeeToFilter;
    window.location = loc;
  }
  reloadShowAll() {
    let loc = '/?exp_traq_name=' + this.traq;
    loc += '&show=all';
    if (this.showAsTable)
      loc += '&showAs=table';
    else
      loc += '&showAs=list';
    if (this.payeeToFilter)
      loc += '&payee=' + this.payeeToFilter;
    window.location = loc;
  }
  reloadShowTopN() {
    let loc = '/?exp_traq_name=' + this.traq;
    if (this.showAsTable)
      loc += '&showAs=table';
    else
      loc += '&showAs=list';
    if (this.payeeToFilter)
      loc += '&payee=' + this.payeeToFilter;
    window.location = loc;    
  }
  // I've added in the html a list of all payees in a tracker.
  // Clicking 'View entries' next to a payee calls this function, which adds 'payee=<payee name>'
  // to the query string and reloads the page. This will show all entries just for this payee.
  reloadAsFilteredByPayee(payeeName) {
    this.payeeToFilter = encodeURIComponent(payeeName);
    let loc = '/?exp_traq_name=' + this.traq;
    if (!this.showTopN)
      loc += '&show=all';
    if (this.showAsTable)
      loc += '&showAs=table';
    // Need to urlencode the payee because nothing precludes the payee name from 
    // having characters that aren't allowed in a URI, such as spaces and ampersands.
    loc += '&payee=' + this.payeeToFilter;
    window.location = loc;
  }

  removePayeeFilter() {
    this.payeeToFilter = "";
    let loc = '/?exp_traq_name=' + this.traq;
    if (!this.showTopN)
      loc += '&show=all';
    if (this.showAsTable)
      loc += '&showAs=table';
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

function showXpostField() {
  document.getElementById('xpostDefault').style.display = 'none';
  document.getElementById('xpostField').style.display = 'flex';
  document.getElementById('xpostInput').focus();
}

function showChangeTraq() {
  document.getElementById('expTraqDefaultView').style.display = 'none';
  document.getElementById('expTraqChangeBtn').style.display = 'none';
  
  var form = document.getElementById('changeTraqForm');
  form.style.display = 'block';
  document.getElementById('changeExpTraqField').focus();
}

// Global... Maybe there's a better way to pass this, but this was easiest...
var idOfEntryBeingEdited; 

// Wrapping the below code in window.addEventListener because this code will only work
// *after* jQuery lib has been loaded, and it gets loaded right before the </body>
// Otherwise it gives error "variable $ not found". Also, editForm needs to have been loaded.
window.addEventListener('load', function() {
  //
  // Adding hook #1: handling user clicking edit, to populate the form with values
  //
  // From https://getbootstrap.com/docs/4.0/components/modal/
  // This is how we instantiate the modal's content from the triggering entry
  $('#editModal').on('show.bs.modal', function (event) {
    var triggerer = $(event.relatedTarget); // Button that triggered the modal
    idOfEntryBeingEdited = triggerer.data('entry-id'); // Extract entry id from triggerer's data-entry-id attribute

    // Now that we have entry id, we use some jQuery to get amount, payee, etc.
    // (recall that jQuery is required by Boostrap, so we get it for free)

    // Note: .amount (which has thouhsands separators) was causing the edit form not
    // to show the amount, since comma is not considered a valid charactre in a number.
    // To fix this, in index.html, I added a hidden element (class='UNFORMATTED-AMOUNT')
    // which holds the unformatted amount (e.g. 1234 instead of $1,234)
    const amount = $('#' + idOfEntryBeingEdited).find('.UNFORMATTED-AMOUNT').text();
    
    const payee = $('#' + idOfEntryBeingEdited).find('.payee').text();
    const date = $('#' + idOfEntryBeingEdited).find('.dateYMD').text();
    const comment = $('#' + idOfEntryBeingEdited).find('.comment').text();
    console.log('Editing: [' + date + '] [' + amount + '] [' + payee + '] [' + comment + ']');
    
    // Update the modal's content. We'll use jQuery here, but could use a data binding library or other methods instead.
    var modal = $(this)
    // Assign amount etc. as values inside the form
    modal.find("[name='amount']").attr('value', amount);
    modal.find("[name='payee']").attr('value', payee);
    modal.find("[name='date']").attr('value', date);
    modal.find("[name='comment']").val(comment);
    //modal.find('.modal-title').text('Editing #' + id)
  });

  //
  // Adding hook #2: intercept edit form submission and handle it OUR way
  //
  document.getElementById('editForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevents form submission; but field validation still takes place

    var ajaxRequest = new XMLHttpRequest();

    // Handle successful completion of the AJAX call
    // This is async and will be called sometime after this current scope exits
    ajaxRequest.onreadystatechange = function() {
      if (ajaxRequest.readyState == 4 && ajaxRequest.status == 200) {
        console.log('Edit request completed successfully; reloading page');
        window.location.reload() // Wasn't sure if I need to reload here, or from python...
      }
    };

    var form = document.getElementById('editForm');
    var formData = new FormData(form); // Get field values from form when form was submitted
    const amount = formData.get('amount');
    const payee = formData.get('payee');
    const date = formData.get('date');
    const comment = formData.get('comment');
    console.log('Will PUT [' + date + '] [' + amount + '] [' + payee + '] [' + comment + ']');

    ajaxRequest.open('PUT', 'entry/' + idOfEntryBeingEdited);
    // From my debugging, turns out webapp2 expects form parameters as application/x-www-form-urlencoded
    ajaxRequest.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    var contentBody = "";
    contentBody += 'amount=' + encodeURIComponent(amount) + '&';
    contentBody += 'payee=' + encodeURIComponent(payee) + '&';
    contentBody += 'date=' + encodeURIComponent(date) + '&';
    contentBody += 'comment=' + encodeURIComponent(comment);
    ajaxRequest.send(contentBody); 
  
    // Not sure this is needed. Seems to work w/o it as well but 
    // some on Stackoverflow say need to return false to prevent default behavior
    return false; 
  });
});

//
// I've added in the html a list of all payees in a tracker. 
// Clicking 'New entry' next to a payee calls this function, to populate the Payee field 
// with the selected payee and place focus into the Amount field.
//
function populatePayeeField(payeeName) {
  document.getElementById("payeeField_mainForm").value = payeeName;
  document.getElementById("amountField_mainForm").focus();
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

function toggleSummaryBoxDetails() {
  var x = document.getElementById("summary_box_details");
  var btn = document.getElementById("show_hide_details_btn");
  if (x.style.display === "none") {
    x.style.display = "block";
    btn.textContent = "Hide details";
  } else {
    x.style.display = "none";
    btn.textContent = "Details";
  }
}


