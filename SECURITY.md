# Security

## Secret handling

Do not commit:

- `.env` files or credential exports;
- Sanity write tokens;
- Google service-account JSON;
- Feishu user tokens or session material;
- vvv App Secret values;
- GitHub tokens or private keys;
- production Feishu tenant, Base, table, view, field or object identifiers;
- production bot application IDs, channel IDs or private endpoint URLs;
- production run artifacts containing private source material.

The vvv sender resolves its secret from `VERTU_VVV_APP_SECRET` or, on macOS,
Keychain service `vertu-vvv-user-robot`. The secret must not appear in command
arguments, prompts, receipts, Feishu rows or logs.

## Production mutations

Production publication must use:

1. a canonical Base start-audit receipt;
2. fresh Sanity schema, author, slug and revision checks;
3. an explicit mutation preview;
4. exact run-scoped document IDs;
5. live verification after mutation;
6. canonical Base article, publication-run and exact-revision QA handoff.

Never retry an ambiguous production POST or mutation blindly.

## Reporting

Report suspected leaks through GitHub private vulnerability reporting when it
is available, or contact the repository owner privately. Rotate affected
credentials before removing leaked history.
