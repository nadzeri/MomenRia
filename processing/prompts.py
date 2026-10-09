import hashlib
import json

from django.conf import settings

from momenria.http import ApiError
from projects.character_sheets import SOURCE_RECIPE


PROMPT_VERSION = "character-v1"
IDENTITY_INSTRUCTIONS = (
    "For every person, the PRIMARY original is the authority for facial proportions, eye spacing, "
    "nose, lips, jaw, visible age, skin tone, hairstyle or head covering, facial hair, glasses and "
    "distinguishing features. SHEET images provide supporting views only; the PRIMARY wins on conflict. "
    "Keep identities distinct. Never average, merge, duplicate or swap people. Preserve natural skin texture."
)
CREATION_INSTRUCTIONS = (
    "Use TEMPLATE only for composition, pose, lighting, background and wardrobe. Replace each template "
    "person with the identity assigned to that slot. Do not copy faces from TEMPLATE. Preserve reference "
    "head coverings; do not reveal hidden hair. Apply only explicitly selected costume accessories."
)
CORRECTION_INSTRUCTIONS = (
    "Use PARENT as the base portrait. Improve likeness only for the target person. Preserve every other "
    "person's identity and appearance, all poses, clothing, accessories, lighting, background, framing "
    "and image dimensions. Do not replace the whole group or copy another slot's identity."
)
NEGATIVE_CONSTRAINTS = (
    "identity drift, a different face, face blending, copied template faces, swapped people, changed facial "
    "proportions, unintended age or hairstyle changes, plastic skin, malformed hands, extra fingers, "
    "extra or missing people, blur, text, logos, watermarks and borders"
)
SHEET_PROMPT = (
    "Create one uncluttered 2 by 2 character reference sheet for the single person in PERSON_PRIMARY. "
    "The uploaded original is the authority for identity. Include a front portrait, a large face close-up, "
    "a three-quarter view and a profile view on a plain neutral background. Preserve the same facial "
    "proportions, visible age, skin tone, hairline, hairstyle or head covering, facial hair, glasses and "
    "distinguishing features in every panel. Keep clothing consistent across the sheet. Use natural skin "
    "texture and neutral lighting. Do not beautify or reinterpret the face. Unseen angles are estimates; "
    "do not introduce new distinguishing marks. Show only this person with no decorative text or logos."
)


def recipe_digest():
    content = [PROMPT_VERSION, SOURCE_RECIPE, IDENTITY_INSTRUCTIONS, CREATION_INSTRUCTIONS, CORRECTION_INSTRUCTIONS, NEGATIVE_CONSTRAINTS, SHEET_PROMPT]
    return hashlib.sha256(json.dumps(content, separators=(",", ":")).encode()).hexdigest()


def validate_character_configuration(template):
    config = template.generation_config
    if config.get("prompt_version") != PROMPT_VERSION or settings.APP_ENV != "production":
        return
    digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if not config.get("capability_verified") or config.get("capability_version", "unverified") == "unverified":
        raise ApiError(503, "gateway_contract_unverified", "Rute referensi karakter belum siap. Coba template lain, ya.")
    if config.get("recipe_digest") != recipe_digest() or template.configuration_hash != digest:
        raise ApiError(503, "configuration_unverified", "Konfigurasi template ini perlu dicek ulang sebelum digunakan.")


def freeze_portrait_prompt(snapshot, template, operation, target_slot_id=None):
    config = snapshot["generation_config"]
    if config.get("prompt_version") != PROMPT_VERSION:
        return
    validate_character_configuration(template)
    snapshot["model"] = config.get("edit_model") if operation == "correction" else config.get("model")
    snapshot["model"] = snapshot["model"] or config.get("model")
    snapshot["gateway_path"] = (config.get("edit_path") if operation == "correction" else None) or config.get("gateway_path")
    if not snapshot["model"] or not snapshot["gateway_path"]:
        raise ApiError(503, "gateway_not_configured", "Rute template ini belum lengkap.")
    snapshot["template"] = {
        "sample_asset": template.sample_asset, "sha256": template.sample_sha256,
        "people_count": template.people_count, "scene": config.get("scene") or template.description,
        "wardrobe_policy": config.get("wardrobe_policy") or template.attire,
        "coordinate_convention": "normalized_center",
    }
    slots = {item["id"]: item for item in snapshot["slots"]}
    roles = [{"role": "parent" if operation == "correction" else "template"}]
    for source in snapshot["sources"]:
        position = int(slots[source["slot_id"]]["position"])
        roles.append({"role": "primary", "source_id": source["source_id"], "slot_id": source["slot_id"], "position": position})
        if source.get("character_sheet"):
            roles.append({"role": "sheet", "sheet_id": source["character_sheet"]["id"], "slot_id": source["slot_id"], "position": position})
    if config.get("reference_order") == "identity_first" and operation != "correction":
        roles = roles[1:] + roles[:1]
    limit = config.get("reference_max_images")
    if type(limit) is not int or limit < 1 or len(roles) > limit:
        raise ApiError(409, "reference_limit_exceeded", "Jumlah referensi melebihi batas rute template ini.")
    snapshot["image_roles"] = [dict(role, index=index) for index, role in enumerate(roles, 1)]
    snapshot["recipe_digest"] = recipe_digest()
    snapshot["capability_version"] = config.get("capability_version", "unverified")
    snapshot["negative_prompt"] = NEGATIVE_CONSTRAINTS if config.get("negative_constraints_enabled", True) else ""
    snapshot["prompt"] = render_portrait_prompt(snapshot, operation, target_slot_id)


def render_portrait_prompt(snapshot, operation, target_slot_id):
    template = snapshot["template"]
    lines = [f"Create one photorealistic portrait with exactly {template['people_count']} people."]
    for image in snapshot["image_roles"]:
        role = image["role"]
        label = f"PERSON_{image['position']}_{role.upper()}" if role in {"primary", "sheet"} else role.upper()
        lines.append(f"Image {image['index']}: {label}.")
    for slot in snapshot["slots"]:
        lines.append(f"PERSON_{slot['position']} belongs to slot {slot['id']}, center ({slot['x']}, {slot['y']}), size ({slot['width']}, {slot['height']}).")
    lines.append("Coordinates are normalized image coordinates; left and right refer to the image, not the subject.")
    lines.append(IDENTITY_INSTRUCTIONS)
    if operation == "correction":
        lines.extend([f"Target slot: {target_slot_id}.", CORRECTION_INSTRUCTIONS])
    else:
        lines.extend([CREATION_INSTRUCTIONS, f"Scene: {template['scene']}", f"Wardrobe and accessory policy: {template['wardrobe_policy']}"])
    if snapshot["negative_prompt"]:
        lines.append(f"Avoid: {snapshot['negative_prompt']}.")
    config = snapshot["generation_config"]
    lines.append(f"Output: one finished portrait, {config.get('output_width', 2048)} by {config.get('output_height', 1536)} pixels.")
    return "\n".join(lines)
