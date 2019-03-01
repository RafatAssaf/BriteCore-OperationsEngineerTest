function contentViewModel() {
    var self = this

    self.policyNumber = ko.observable("").extend({
        required: true,
        maxLength: 128 // from model definition
    })
    let d = new Date()
    let formattedDateString = d.getFullYear() + '-' + ("0" + (d.getMonth() + 1)).slice(-2) + '-' + ("0" + d.getDate()).slice(-2)

    let validateDate = function(d) {
        return moment(d).isBefore(moment())
    }

    self.dateCursor = ko.observable(formattedDateString).extend({
        // custom validator
        validation: {
            validator: validateDate,
            message: 'Invalid date. this software can not predict future. yet.'
        }
    })
    self.invoices = ko.observable(null)
    self.policy = ko.observable({
        account_balance: null
    })

    self.lookupPolicy = function(args) {
        if(self.policyNumber.isValid() && self.dateCursor.isValid()) {
            $.getJSON( $SCRIPT_ROOT + 'policy', {
                policyNumber: self.policyNumber(),
                dateCursor: self.dateCursor()
            }, function(data) {
                console.log(data) // to check response in the console
                self.invoices(data.invoices)
                self.policy(data.policy)
            });
            return false
        }
    }

    self.log = function() {
        console.log(self.policyNumber.isValid())
    }
}

ko.applyBindings(new contentViewModel(), document.getElementById('main'));