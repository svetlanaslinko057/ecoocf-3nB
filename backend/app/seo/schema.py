"""
JSON-LD (schema.org) builders — config-driven, never fabricate facts.

All company facts (legal name, license, address, geo, contacts) come from a
`company` dict assembled by the caller from admin-managed settings. Missing
values are simply omitted (no placeholders leak into structured data).

Builders return plain dicts; the caller serializes them to
<script type="application/ld+json">.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _prune(d: Dict[str, Any]) -> Dict[str, Any]:
    """Drop empty values recursively so schema stays clean/valid."""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            v = _prune(v)
            if not v:
                continue
        elif isinstance(v, list):
            v = [_prune(x) if isinstance(x, dict) else x for x in v if x not in (None, "", {})]
            if not v:
                continue
        elif v in (None, ""):
            continue
        out[k] = v
    return out


def postal_address(company: Dict[str, Any]) -> Dict[str, Any]:
    return _prune({
        "@type": "PostalAddress",
        "streetAddress": company.get("street"),
        "addressLocality": company.get("city"),
        "addressRegion": company.get("region"),
        "postalCode": company.get("postal_code"),
        "addressCountry": company.get("country") or "UA",
    })


def contact_point(company: Dict[str, Any]) -> Dict[str, Any]:
    phones = company.get("phones") or ([company["phone"]] if company.get("phone") else [])
    return _prune({
        "@type": "ContactPoint",
        "telephone": phones[0] if phones else None,
        "email": company.get("email"),
        "contactType": "customer service",
        "areaServed": "UA",
        "availableLanguage": ["uk", "en"],
    })


def organization(company: Dict[str, Any], origin: str) -> Dict[str, Any]:
    node = {
        "@type": ["Organization", "ProfessionalService"],
        "@id": f"{origin}/#organization",
        "name": company.get("name") or "ECO.NOVA",
        "legalName": company.get("legal_name"),
        "url": origin or None,
        "logo": _prune({
            "@type": "ImageObject",
            "url": company.get("logo") or (f"{origin}/android-chrome-512x512.png" if origin else None),
        }) or None,
        "email": company.get("email"),
        "telephone": (company.get("phones") or [company.get("phone")])[0] if (company.get("phones") or company.get("phone")) else None,
        "address": postal_address(company) or None,
        "contactPoint": [contact_point(company)] if contact_point(company) else None,
        "vatID": company.get("edrpou"),
        "taxID": company.get("edrpou"),
        "foundingDate": company.get("founding_date"),
        "areaServed": {"@type": "Country", "name": "Ukraine"},
        "sameAs": company.get("same_as") or None,
        "description": company.get("description"),
    }
    # License / accreditation — only when a real number is provided.
    if company.get("license_number"):
        node["hasCredential"] = _prune({
            "@type": "EducationalOccupationalCredential",
            "credentialCategory": "license",
            "name": company.get("license_name") or "Ліцензія на поводження з небезпечними відходами",
            "identifier": company.get("license_number"),
        })
    geo = None
    if company.get("lat") and company.get("lng"):
        geo = {"@type": "GeoCoordinates", "latitude": company["lat"], "longitude": company["lng"]}
    if geo:
        node["geo"] = geo
    return _prune(node)


def local_business(company: Dict[str, Any], origin: str) -> Dict[str, Any]:
    node = organization(company, origin)
    node["@type"] = ["LocalBusiness"]
    node["@id"] = f"{origin}/#localbusiness"
    if company.get("opening_hours"):
        node["openingHours"] = company["opening_hours"]
    if company.get("price_range"):
        node["priceRange"] = company["price_range"]
    return _prune(node)


def website(origin: str, name: str = "ECO.NOVA") -> Dict[str, Any]:
    return _prune({
        "@type": "WebSite",
        "@id": f"{origin}/#website",
        "url": origin or None,
        "name": name,
        "inLanguage": ["uk", "en"],
        "publisher": {"@id": f"{origin}/#organization"},
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{origin}/waste?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    })


def web_page(origin: str, url: str, title: str, description: str,
             lang: str, published: Optional[str] = None,
             updated: Optional[str] = None,
             breadcrumb_id: Optional[str] = None) -> Dict[str, Any]:
    return _prune({
        "@type": "WebPage",
        "@id": f"{url}#webpage",
        "url": url,
        "name": title,
        "description": description,
        "inLanguage": lang,
        "isPartOf": {"@id": f"{origin}/#website"},
        "datePublished": published,
        "dateModified": updated,
        "breadcrumb": {"@id": breadcrumb_id} if breadcrumb_id else None,
    })


def breadcrumb_list(items: List[Dict[str, str]], url: str) -> Dict[str, Any]:
    return {
        "@type": "BreadcrumbList",
        "@id": f"{url}#breadcrumb",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": it["name"],
                "item": it["url"],
            }
            for i, it in enumerate(items)
        ],
    }


def service(name: str, description: str, origin: str, url: str,
            area: str = "Ukraine") -> Dict[str, Any]:
    return _prune({
        "@type": "Service",
        "serviceType": name,
        "name": name,
        "description": description,
        "provider": {"@id": f"{origin}/#organization"},
        "areaServed": {"@type": "Country", "name": area},
        "url": url,
    })


def faq_page(qa: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in qa if item.get("q") and item.get("a")
        ],
    }


def article(origin: str, url: str, title: str, description: str,
            image: Optional[str], published: Optional[str],
            updated: Optional[str], author: Optional[str],
            lang: str) -> Dict[str, Any]:
    return _prune({
        "@type": "Article",
        "headline": title[:110],
        "description": description,
        "image": image,
        "inLanguage": lang,
        "datePublished": published,
        "dateModified": updated or published,
        "author": {"@type": "Person", "name": author} if author else {"@id": f"{origin}/#organization"},
        "publisher": {"@id": f"{origin}/#organization"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    })


def software_application(origin: str, url: str, name: str, description: str) -> Dict[str, Any]:
    return _prune({
        "@type": "SoftwareApplication",
        "name": name,
        "description": description,
        "url": url,
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "UAH"},
        "provider": {"@id": f"{origin}/#organization"},
    })


def graph(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Wrap nodes into a single @graph document."""
    return {"@context": "https://schema.org", "@graph": [n for n in nodes if n]}
