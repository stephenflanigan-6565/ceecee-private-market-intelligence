# PMI property review workspace

Open `/review/` on the SeaLion app. This is the seller-first workspace: a small research pilot, a separate seller inquiry queue, source evidence, working notes, and reviewed case memory. No outside AI account or subscription is required.

## One-time DigitalOcean setup

1. Open **sea-lion-app → Settings → App-Level Environment Variables → Edit**.
2. Add `PMI_REVIEW_ACCESS_KEY`. Choose a private passphrase of at least 24 characters, enable **Encrypt**, and make it available at runtime. This is the password for the new review area, not a service API key. Do not paste it into a chat, source file, or URL.
3. Save and let the app redeploy. Keep the app's existing PostgreSQL `DATABASE_URL` setting.
4. Open `/review/`, enter the passphrase, and choose **Prepare workspace**. This authenticated action creates only the new review and memory tables.
5. Choose **Load property records** to import the complete existing research. Earlier source snapshots, notes, evidence, corrections, and review events stay in the database.

Without the passphrase configuration, the review area displays a locked setup page and does not access property records or create tables. The new workflow requires PostgreSQL in production; it does not fall back to a temporary app-container database.

## First session

Start in **Research pilot**, which holds up to five supported property research cases. The initial selection is a deterministic sample, not a seller ranking. You can remove a case from your pilot and select another supported property.

Open a property and read why it surfaced, the next useful check, and the retained findings. A property's research merit is separate from evidence that its owner plans to sell. Reported owner names remain unverified unless an attributed source establishes the connection. Missing owner information does not discard an address-based opportunity.

Use **Your workflow** to set a stage and record the next step. These notes preserve work without becoming verified seller evidence. Case history keeps earlier notes and changes.

Use **Sources & observations** to capture a specific property fact or an attributed public/authorized statement. Keep its source reference and date. Mark it verified only after checking it. Source links are locators; PMI does not automatically read or fetch them. State whether a statement actually refers to this property. Buying interest or a change in circumstances alone does not establish a sale obligation.

When the engine has an explanation, use **Record your finding about this explanation**. Select the outcome and how it was checked, then preserve the supporting details. Confirming a seller's reason requires the owner's own disclosure. Verified negative findings hold the same explanation on later analyses; duplicate captures do not erase that result.

Correct source records by entering the earlier evidence record reference. Original and corrected entries remain in history. **Download workspace record** provides a private JSON backup containing imports, cases, evidence, reviewed findings, and reasoning snapshots. Treat that file as owner/property information.

Seller inquiries can be empty when evidence is insufficient. All imported properties remain accessible through **All properties**, including held explanations. This workflow sends no marketing or owner contact.

## Local preview

Install the repository requirements, set the same private passphrase environment variable, and run:

```sh
python review_preview.py --input /absolute/path/find4-complete.json --database /absolute/path/review-pilot.db
```

Open `http://127.0.0.1:8090/review/`. The preview binds to loopback and explicitly permits local HTTP cookies. Ordinary GET requests do not initialize, import, or write analyses. PostgreSQL and SQLite use the same append-only review contract; schema initialization remains an explicit action.

The authentication boundary covers the new `/review` workspace. Existing historical diagnostic endpoints retain their previous behavior.
