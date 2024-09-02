This is a quick doc to hash out a draft for the `regex_accountant`
query syntax for filtering, tagging, and linking transactions.

I imagine the basic syntax as a pipeline model, where you have a
sequence of operations that happen one after the other, and the output
from each operation is used as the input for the one that comes after.

Kind of like [LogQL](https://grafana.com/docs/loki/latest/query/)...
except hopefully less of a bear to use. I want something that will be
easy to type out concisely and accurately in real time.

## Basic filtering

```
acct=venmo date>=2024-02
```

That will generate a list of all transactions starting from February
2024 where `account` is `venmo` exactly. For filtering, you can
combine any number of selectors conjunctively. The special characters
you use determine how the values are interpreted:

* `=` exact matching, case insensitive
* `==` exact matching, case sensitive
* `:` substring matching, case insensitive
* `::` substring matching, case sensitive
* `<` `>` `<=` `>=` date or number or string comparison
* `~` regex matching, case sensitivity controlled by flags

You can prefix any of those operators with `!` to invert the meaning,
so `!::` would say that a field must NOT contain a particular
substring (case sensitive). Or you can prefix the whole selector with
`-` to achieve the same. If you omit the operator and value, then it
is filtering for the field being set at all.

Normally multiple selectors are separated with whitespace. If you need
to filter on a value with whitespace, you can quote it (single or
double quotes). Double quotes are standard C strings, backslash for
escapes; single quotes are raw strings and all characters are
interpreted literally except for single quotes, which can be
duplicated to escape them.

You can separate selectors with `and` / `or` matchers, standard C
precedence, and an omitted boolean operator between two selectors is
interpreted as `and`. Parens can be used to override precedence. Note
that regex matching may be a viable alternative for disjunction in
simple cases.

Any of the standard field names in a transaction object can be
filtered on, and there are predefined shorthands such as `acct` for
`account`.

## Applying labels

```
acct=fidelity desc:safeway.com -cat | set cat=Food:Grocery:Safeway
```

A pipeline is composed of multiple operations separated by `|`
characters. An operation has a command and then arguments. You can
omit the command to have it default to `filter` since that's the most
common.

Pipelines start with a selection on all transactions in chronological
order. The pipeline above takes all transactions, filters them to only
the Safeway transactions not already categorized, and then applies an
identifying label. This actually supports overriding any property of a
transaction (with results reflected in the displayed data, but not
mutating the original database - so you can change these rules at any
time to see updated output), and you can define in your ruleset what
additional properties (such as `cat`, short for `category`) ought to
be supported for setting.

## Sorting results

```
-cat | sort abs(amt) desc
```

You can sort by any arithmetic expression based on transaction field
properties, note that this does not transform any data outside the
current pipeline (unlike the `set` operation).

This example shows the largest uncategorized transactions and would be
a good interactive view for importing new data.

You can filter on multiple fields lexicographically to handle ties,
just add them as further arguments. Sorting precedence is left to
right. You can omit or supply `asc`/`desc` for each, the default is
`asc`.

## Linking transactions

```
acct=paypal meth:elevations | join acct=elevations desc:paypalsi77
  date>=a.date date<=a.date+5d amt=a.amt | set b.src=a a.alias=t
```

This is where things start to get interesting. The `join` operation
iterates through each transaction from the input, and performs a query
over the full transaction set to find another transaction that matches
it. The filtering selectors in the `join` can refer to field values
from the transaction being matched against. If no prefix is given then
the field values refer to the current transaction based on where we
are in the pipeline. Otherwise, the `a.` prefix explicitly identifies
the first transaction in the pipeline, `b.` identifies the second, and
so on through the alphabet.

Matching can be one-to-one (`join`) or one-to-many (`joins`). The
lettering scheme remains unchanged. Once you've got additional
transaction(s) in scope from `join`, you can refer to their fields in
`set`. There is a custom field type that can be set to a transaction
reference, and another that can be set to a list of transaction
references.

So, the example above is looking for PayPal transactions that use
Elevations as a payment method, then one-to-one matching them to
corresponding-looking Elevations transactions. There is some leeway
given in the date matching because sometimes transactions take time to
clear. But the amounts must match. Then once a match is found, the
Elevations transaction has a field defined that points at the PayPal
transaction, and the PayPal transaction is marked as an alias (this
would be a user-defined concept designed to filter out duplicates and
only show one copy of each transaction). If a transaction has custom
fields that get assigned to valid references, then all the data from
linked transactions in those fields will be shown in the user
interface, and you can reference the nested fields in subsequent query
operations, too.

Note that transaction references are truly references (or pointers),
not data copies. So, if you need to link together a chain of
transactions, you can do so in any order, you don't need to worry
about linking the most nested ones first.
