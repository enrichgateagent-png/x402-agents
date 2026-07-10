// Compliance lookups against authoritative free registries:
// EU VIES (VAT validation) and GLEIF (LEI / legal entity lookup).

async function getJson(url: string) {
  const res = await fetch(url, { signal: AbortSignal.timeout(15000), headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`Upstream ${new URL(url).hostname} returned ${res.status}`);
  return res.json();
}

const EU_COUNTRIES = new Set("AT BE BG CY CZ DE DK EE EL ES FI FR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK XI".split(" "));

export async function vatCheck(countryCode: string, vatNumber: string) {
  const cc = countryCode.toUpperCase();
  if (!EU_COUNTRIES.has(cc)) throw new Error(`countryCode must be an EU code: ${[...EU_COUNTRIES].join(", ")}`);
  const clean = vatNumber.replace(/[^0-9A-Za-z+*]/g, "");
  const data: any = await getJson(`https://ec.europa.eu/taxation_customs/vies/rest-api/ms/${cc}/vat/${encodeURIComponent(clean)}`);
  return {
    valid: data.isValid === true,
    countryCode: cc,
    vatNumber: clean,
    name: data.name && data.name !== "---" ? data.name : null,
    address: data.address && data.address !== "---" ? data.address.replace(/\n/g, ", ") : null,
    checkedAt: data.requestDate,
    source: "EU VIES (authoritative)",
  };
}

export async function leiLookup(params: { lei?: string; name?: string }, limit = 5) {
  const url = params.lei
    ? `https://api.gleif.org/api/v1/lei-records/${encodeURIComponent(params.lei.toUpperCase())}`
    : `https://api.gleif.org/api/v1/lei-records?filter%5Bentity.legalName%5D=${encodeURIComponent(params.name!)}&page%5Bsize%5D=${limit}`;
  const data: any = await getJson(url);
  const records = Array.isArray(data.data) ? data.data : [data.data];
  return {
    total: data.meta?.pagination?.total ?? records.length,
    entities: records.filter(Boolean).map((r: any) => ({
      lei: r.id,
      name: r.attributes?.entity?.legalName?.name,
      jurisdiction: r.attributes?.entity?.jurisdiction,
      status: r.attributes?.entity?.status,
      registrationStatus: r.attributes?.registration?.status,
      address: [
        r.attributes?.entity?.legalAddress?.addressLines?.join(", "),
        r.attributes?.entity?.legalAddress?.city,
        r.attributes?.entity?.legalAddress?.country,
      ]
        .filter(Boolean)
        .join(", "),
    })),
    source: "GLEIF (authoritative)",
  };
}
