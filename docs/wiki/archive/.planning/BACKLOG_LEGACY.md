
## Future Sprints: Directus Integration
- [ ] **Deploy Directus:** Re-enable Directus in `docker-compose.coolify.yml`.
- [ ] **Configure Storage Mount:** Ensure Directus maps its local file storage to the exact same `/mnt/block_storage/evidence_drop` volume used by the MCP Node backend.
- [ ] **Create Directus Flow (Webhook):** Set up a trigger in Directus that fires on `file.create`.
- [ ] **Wire Webhook to API:** Have the Directus Flow send an HTTP POST to `https://api.mitechconsult.com/trpc/ingestion.ingestLocalFile` with the absolute path of the uploaded file.
- [ ] **PhotoPrism Integration:** Re-enable PhotoPrism and map it to the same MySQL database and Block Storage volume for automated image AI processing.
