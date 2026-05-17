//! Caddy admin-API integration for preview routing.
//!
//! The daemon POSTs a `reverse_proxy` route into Caddy's running config for
//! each ready preview, and DELETEs it on teardown. Caddy must already have an
//! HTTP server (default name `srv0`) configured; route registration is
//! best-effort — a missing Caddy is logged, not fatal (see
//! [`super::localdocker::LocalDocker::deploy_preview`]).

use anyhow::{Context, Result};
use serde_json::{json, Value};

/// A DNS-label-safe slug of a job id (`fj_01H...` → `fj-01h...`): lowercase
/// ASCII alphanumerics, every other byte replaced with `-`.
pub fn host_label(job_id: &str) -> String {
    job_id
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() {
                c.to_ascii_lowercase()
            } else {
                '-'
            }
        })
        .collect()
}

/// The Caddy route `@id` for a job's preview route.
pub fn route_id(job_id: &str) -> String {
    format!("foundry-preview-{}", host_label(job_id))
}

/// The hostname a preview is served under.
///
/// With an `org_slug` the preview is namespaced per organization —
/// `<app_name>.<org_slug>.<root_domain>` — so each org's builds live under
/// their own subdomain. Without one it is `<app_name>.<root_domain>`
/// (unchanged, backward compatible). `app_name` and `org_slug` are both
/// validated lowercase `[a-z0-9-]` slugs (DNS-safe labels), so they are used
/// directly. Knowmler generates a playful, app-derived `app_name`, so a
/// preview lands at e.g. `wishful-stickers.acme.knowmler.com`. The Caddy
/// route `@id` keys off the job id (`route_id`), which stays unique even if
/// two apps share a name.
pub fn preview_hostname(app_name: &str, org_slug: Option<&str>, root_domain: &str) -> String {
    match org_slug {
        Some(slug) => format!("{}.{}.{}", app_name, slug, root_domain),
        None => format!("{}.{}", app_name, root_domain),
    }
}

/// The full `https://` preview URL stored on the job.
///
/// `https`, not `http`: previews are always served through a TLS-terminating
/// reverse proxy (Caddy). Knowmler links/embeds this URL from an HTTPS page,
/// so an `http://` value would be a mixed-content failure.
pub fn preview_url(app_name: &str, org_slug: Option<&str>, root_domain: &str) -> String {
    format!("https://{}", preview_hostname(app_name, org_slug, root_domain))
}

/// The Caddy route object reverse-proxying `hostname` to `upstream`
/// (a `host:port` dial string).
pub fn route_json(job_id: &str, hostname: &str, upstream: &str) -> Value {
    json!({
        "@id": route_id(job_id),
        "match": [{ "host": [hostname] }],
        "handle": [{
            "handler": "reverse_proxy",
            "upstreams": [{ "dial": upstream }]
        }]
    })
}

/// POST a preview route into Caddy's running config (appends to the routes
/// array of `server`).
pub async fn add_route(
    admin_url: &str,
    server: &str,
    job_id: &str,
    hostname: &str,
    upstream: &str,
) -> Result<()> {
    let url = format!(
        "{}/config/apps/http/servers/{}/routes",
        admin_url.trim_end_matches('/'),
        server
    );
    let resp = reqwest::Client::new()
        .post(&url)
        .json(&route_json(job_id, hostname, upstream))
        .send()
        .await
        .context("POST Caddy route")?;
    if !resp.status().is_success() {
        anyhow::bail!("Caddy route add returned HTTP {}", resp.status());
    }
    Ok(())
}

/// DELETE a previously-added preview route by its `@id`. A 404/400 (the route
/// was never registered) is not an error worth surfacing.
pub async fn remove_route(admin_url: &str, job_id: &str) -> Result<()> {
    let url = format!(
        "{}/id/{}",
        admin_url.trim_end_matches('/'),
        route_id(job_id)
    );
    let _ = reqwest::Client::new()
        .delete(&url)
        .send()
        .await
        .context("DELETE Caddy route")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn host_label_is_dns_safe() {
        let label = host_label("fj_01HMX");
        assert_eq!(label, "fj-01hmx");
        assert!(!label.contains('_'));
        assert_eq!(label, label.to_lowercase());
    }

    #[test]
    fn route_id_and_hostname_are_derived() {
        // route_id is keyed by the job id (unique); the hostname uses the
        // app_name slug — the playful, app-derived label Knowmler generates.
        assert_eq!(route_id("fj_1"), "foundry-preview-fj-1");
        // No org slug: <app>.<root> (backward compatible).
        assert_eq!(
            preview_hostname("wishful-stickers", None, "knowmler.com"),
            "wishful-stickers.knowmler.com"
        );
        assert_eq!(
            preview_url("wishful-stickers", None, "knowmler.com"),
            "https://wishful-stickers.knowmler.com"
        );
        // With an org slug: <app>.<org>.<root>.
        assert_eq!(
            preview_hostname("wishful-stickers", Some("acme"), "knowmler.com"),
            "wishful-stickers.acme.knowmler.com"
        );
        assert_eq!(
            preview_url("wishful-stickers", Some("acme"), "knowmler.com"),
            "https://wishful-stickers.acme.knowmler.com"
        );
    }

    #[test]
    fn route_json_reverse_proxies_to_upstream() {
        let r = route_json("fj_1", "build-fj-1.foundry.local", "127.0.0.1:49160");
        assert_eq!(r["@id"], "foundry-preview-fj-1");
        assert_eq!(r["match"][0]["host"][0], "build-fj-1.foundry.local");
        assert_eq!(r["handle"][0]["handler"], "reverse_proxy");
        assert_eq!(r["handle"][0]["upstreams"][0]["dial"], "127.0.0.1:49160");
    }
}
