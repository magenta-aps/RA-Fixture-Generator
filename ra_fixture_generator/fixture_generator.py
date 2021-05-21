#!/usr/bin/env python3
# --------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2021 Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
# --------------------------------------------------------------------------------------
import click
from itertools import chain
from itertools import groupby
from itertools import zip_longest
from more_itertools import flatten
from more_itertools import prepend
from more_itertools import ilen
from more_itertools import take
from operator import itemgetter
from operator import add
import random

from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

from ramodels.lora import Facet
from ramodels.lora import Klasse
from ramodels.lora import Organisation
from ramodels.mo import Address
# from ramodels.mo import Association
from ramodels.mo import Employee
from ramodels.mo import Engagement
from ramodels.mo import Manager
from ramodels.mo import OrganisationUnit

from mimesis import Code
from mimesis import Internet
from mimesis import Person
from mimesis.builtins.base import BaseSpecProvider
from mimesis.enums import EANFormat
from mimesis.builtins import DenmarkSpecProvider
from mimesis.enums import Gender

from apply import apply

from ra_flatfile_importer.lora_flatfile_model import LoraFlatFileFormat
from ra_flatfile_importer.lora_flatfile_model import LoraFlatFileFormatChunk
from ra_flatfile_importer.mo_flatfile_model import MOFlatFileFormat
from ra_flatfile_importer.mo_flatfile_model import MOFlatFileFormatChunk
from ra_flatfile_importer.util import generate_uuid as unseeded_generate_uuid

from ra_fixture_generator.generate_org_tree import gen_org_tree, tree_visitor

CLASSES: Dict[str, List[Union[Tuple[str, str, str], str]]] = {
    "engagement_job_function": [
        "Udvikler",
        "Specialkonsulent",
        "Ergoterapeut",
        "Udviklingskonsulent",
        "Specialist",
        "Jurist",
        "Personalekonsulent",
        "Lønkonsulent",
        "Kontorelev",
        "Ressourcepædagog",
        "Pædagoisk vejleder",
        "Skolepsykolog",
        "Støttepædagog",
        "Bogopsætter",
        "Timelønnet lærer",
        "Pædagogmedhjælper",
        "Teknisk Servicemedarb.",
        "Lærer/Overlærer",
    ],
    "association_type": [
        "Formand",
        "Leder",
        "Medarbejder",
        "Næstformand",
        "Projektleder",
        "Projektgruppemedlem",
        "Teammedarbejder",
    ],
    "org_unit_type": [
        "Afdeling",
        "Institutionsafsnit",
        "Institution",
        "Fagligt center",
        "Direktørområde",
    ],
    "org_unit_level": ["N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"],
    "responsibility": [
        "Personale: ansættelse/afskedigelse",
        "Beredskabsledelse",
        "Personale: øvrige administrative opgaver",
        "Personale: Sygefravær",
        "Ansvar for bygninger og arealer",
        "Personale: MUS-kompetence",
    ],
    "manager_type": [
        "Direktør",
        "Distriktsleder",
        "Beredskabschef",
        "Sekretariatschef",
        "Systemadministrator",
        "Områdeleder",
        "Centerchef",
        "Institutionsleder",
    ],
    "role_type": [
        "Tillidsrepræsentant",
        "Ergonomiambasadør",
        "Ansvarlig for sommerfest",
    ],
    "leave_type": [
        "Barselsorlov",
        "Forældreorlov",
        "Orlov til pasning af syg pårørende",
    ],
    "employee_address_type": [
        ("AdressePostEmployee", "Postadresse", "DAR"),
        ("PhoneEmployee", "Telefon", "PHONE"),
        ("LocationEmployee", "Lokation", "TEXT"),
        ("EmailEmployee", "Email", "EMAIL"),
    ],
    "manager_address_type": [
        ("EmailManager", "Email", "EMAIL"),
        ("TelefonManager", "Telefon", "PHONE"),
        ("AdressePostManager", "Adresse", "DAR"),
        ("WebManager", "Webadresse", "TEXT"),
    ],
    "org_unit_address_type": [
        ("AddressMailUnit", "Postadresse", "DAR"),
        ("AdressePostRetur", "Returadresse", "DAR"),
        ("AdresseHenvendelsessted", "Henvendelsessted", "DAR"),
        ("LocationUnit", "Lokation", "TEXT"),
        ("Skolekode", "Skolekode", "TEXT"),
        ("Formålskode", "Formålskode", "TEXT"),
        ("Afdelingskode", "Afdelingskode", "TEXT"),
        ("EmailUnit", "Email", "EMAIL"),
        ("PhoneUnit", "Telefon", "PHONE"),
        ("FaxUnit", "Fax", "PHONE"),
        ("EAN", "EAN-nummer", "EAN"),
        ("WebUnit", "Webadresse", "WWW"),
        ("p-nummer", "P-nummer", "PNUMBER"),
    ],
    "manager_level": ["Niveau 1", "Niveau 2", "Niveau 3", "Niveau 4"],
    "time_planning": ["Arbejdstidsplaner", "Dannes ikke", "Tjenestetid"],
    "engagement_type": ["Ansat"],
    "visibility": [
        ("Ekstern", "Må vises eksternt", "PUBLIC"),
        ("Intern", "Må vises internt", "INTERNAL"),
        ("Hemmelig", "Hemmelig", "SECRET"),
    ],
    "primary_type": [
        ("explicitly-primary", "Manuelt primær ansættelse", "5000"),
        ("primary", "Primær", "3000"),
        ("non-primary", "Ikke-primær ansættelse", "0"),
    ],
    "org_unit_hierarchy": [],
}

for facetbvn, classes in CLASSES.items():
    CLASSES[facetbvn] = list(map(
        lambda clazz: clazz if isinstance(clazz, tuple) else (clazz, clazz, "TEXT"),
        classes
    ))


def generate_facets_and_classes(generate_uuid, organisation) -> Tuple[List[Facet], List[Klasse]]:
    def construct_facets(facetbvn):
        facet = Facet.from_simplified_fields(
            uuid=generate_uuid(facetbvn),
            user_key=facetbvn,
            organisation_uuid=organisation.uuid,
        )
        return facet

    @apply
    def construct_class(facetbvn, user_key, title, scope):
        klasse = Klasse.from_simplified_fields(
            facet_uuid=generate_uuid(facetbvn),
            uuid=generate_uuid(user_key),
            user_key=user_key,
            title=title,
            scope=scope,
            organisation_uuid=organisation.uuid,
        )
        return klasse

    def yield_class():
        for facetbvn, classes in CLASSES.items():
            for user_key, title, scope in classes:
                yield facetbvn, user_key, title, scope
 
    facets = list(map(construct_facets, CLASSES.keys()))
    klasses = list(map(construct_class, yield_class()))
    return facets, klasses


def generate_org_units(generate_uuid, org_tree):
    def construct_org_unit(name, level, prefix) -> Tuple[int, OrganisationUnit]:
        parent_uuid = None
        if prefix:
            parent_uuid=generate_uuid("org_unit" + prefix)

        return level, OrganisationUnit.from_simplified_fields(
            uuid=generate_uuid("org_unit" + prefix + name),
            user_key=name,
            name=name,
            org_unit_type_uuid=generate_uuid("Afdeling"),
            org_unit_level_uuid=generate_uuid("N" + str(level)),
            parent_uuid=parent_uuid,
        )

    model_tree = list(tree_visitor(org_tree, construct_org_unit))
    model_layers = groupby(sorted(model_tree, key=itemgetter(0)), itemgetter(0))

    layers = []
    for level, model_layer in model_layers:
        layer = list(map(itemgetter(1), model_layer))
        layers.append(layer)
    return layers

class PNummer(BaseSpecProvider):
    class Meta:
        name = "pnummer"

    def _gen_x_digit_number(self, n: int) -> str:
        assert n > 0
        number = self.random.randint(0, 10**n-1)
        return str(number).zfill(n)

    def pnumber(self) -> str:
        return self._gen_x_digit_number(10)


def generate_org_addresses(generate_uuid, seed, org_layers):
    code_gen = Code(seed=seed)
    internet_gen = Internet(seed=seed)
    person_gen = Person('da', seed=seed)
    pnummer_gen = PNummer(seed=seed)

    def construct_addresses(org_unit):
        org_unit_uuid = org_unit.uuid

        addresses = [
            # TODO: dar_uuid needs to be valid, fetch from DAR?
            #(generate_uuid("fake-dar-1" + str(org_unit_uuid)), generate_uuid("AdresseMailUnit")),
            #(generate_uuid("fake-dar-2" + str(org_unit_uuid)), generate_uuid("AdresseHenvendelsessted")),
            #(generate_uuid("fake-dar-3" + str(org_unit_uuid)), generate_uuid("AdressePostRetur")),
            (person_gen.telephone("########"), generate_uuid("FaxUnit")),
            (person_gen.telephone("########"), generate_uuid("PhoneUnit")),
            (person_gen.email(), generate_uuid("EmailUnit")),
            (code_gen.ean(EANFormat.EAN13), generate_uuid('EAN')),
            (pnummer_gen.pnumber(), generate_uuid('p-nummer')),
            ("Bygning {}".format(random.randrange(1, 20)), generate_uuid('LocationUnit')),
            (internet_gen.home_page(), generate_uuid('WebUnit')),
        ]

        return [
            Address.from_simplified_fields(
                uuid=generate_uuid(str(org_unit_uuid) + str(value)),
                value=str(value),
                value2=None,
                address_type_uuid=address_type_uuid,
                org_uuid=generate_uuid(""),
                from_date="1930-01-01",
                org_unit_uuid=org_unit_uuid,
            ) for value, address_type_uuid in addresses
        ]

    return [
        list(flatten(map(construct_addresses, layer))) for layer in org_layers
    ]


def generate_employees(generate_uuid, seed, org_layers):
    person_gen = Person('da', seed=seed)
    danish_gen = DenmarkSpecProvider(seed=seed)

    num_orgs = ilen(flatten(org_layers))
    num_employees_per_org = 5

    def generate_employee(_):
        def even(x: int) -> bool:
            return (x % 2) == 0

        cpr = danish_gen.cpr()

        gender = Gender.MALE
        if even(int(cpr[-1])):
            gender = Gender.FEMALE

        name = person_gen.full_name(gender=gender)

        return Employee(
            uuid=generate_uuid(cpr),
            name=name,
            # TODO: Reactivate after: mimesis 5.0
            # cpr_no=cpr,
        )

    return list(map(generate_employee, range(num_employees_per_org * num_orgs)))


def generate_employee_addresses(generate_uuid, seed, employees):
    code_gen = Code(seed=seed)
    internet_gen = Internet(seed=seed)
    person_gen = Person('da', seed=seed)
    pnummer_gen = PNummer(seed=seed)

    def construct_addresses(employee):
        employee_uuid = employee.uuid

        addresses = [
            # TODO: dar_uuid needs to be valid, fetch from DAR?
            #(generate_uuid("fake-dar-1" + str(employee_uuid)), generate_uuid("AdressePostEmployee")),
            (person_gen.email(), generate_uuid("EmailEmployee")),
            (person_gen.telephone("########"), generate_uuid("PhoneEmployee")),
            ("Bygning {}".format(random.randrange(1, 20)), generate_uuid('LocationEmployee')),
        ]

        return [
            Address.from_simplified_fields(
                uuid=generate_uuid(str(employee_uuid) + str(value)),
                value=str(value),
                value2=None,
                address_type_uuid=address_type_uuid,
                org_uuid=generate_uuid(""),
                from_date="1930-01-01",
                person_uuid=employee_uuid,
            ) for value, address_type_uuid in addresses
        ]

    return list(flatten(map(construct_addresses, employees)))


def generate_engagements(generate_uuid, employees, org_layers):

    def construct_engagement(employee, org_unit):
        employee_uuid = employee.uuid
        org_unit_uuid = org_unit.uuid

        job_function = random.choice(CLASSES['engagement_job_function'])[0]
        job_function_uuid = generate_uuid(job_function)

        uuid = generate_uuid(str(employee_uuid) + str(org_unit_uuid) + str(job_function_uuid))

        return Engagement.from_simplified_fields(
            uuid=uuid,
            org_unit_uuid=org_unit_uuid,
            person_uuid=employee_uuid,
            job_function_uuid=job_function_uuid,
            engagement_type_uuid=generate_uuid("Ansat"),
            from_date="1930-01-01",
            to_date=None,
            primary_uuid=generate_uuid("primary"),
            user_key=str(uuid)[:8],
        )

    num_employees_per_org = 5
    employee_iter = iter(employees)

    def construct_engagements(org_unit):
        org_employees = take(num_employees_per_org, employee_iter)
        assert len(org_employees) == num_employees_per_org
        return [construct_engagement(employee, org_unit) for employee in org_employees]

    return_value = list(list(flatten(map(construct_engagements, layer))) for layer in org_layers)
    # Ensure all employees were consumed
    assert ilen(employee_iter) == 0
    return return_value


def generate_managers(generate_uuid, employees, org_layers):

    num_employees_per_org = 5
    employee_iter = iter(employees)

    def construct_manager(org_unit):
        org_employees = take(num_employees_per_org, employee_iter)
        assert len(org_employees) == num_employees_per_org

        employee = random.choice(org_employees)

        employee_uuid = employee.uuid
        org_unit_uuid = org_unit.uuid

        responsibility = random.choice(CLASSES['responsibility'])[0]
        responsibility_uuid = generate_uuid(responsibility)

        manager_level = random.choice(CLASSES['manager_level'])[0]
        manager_level_uuid = generate_uuid(manager_level)

        manager_type = random.choice(CLASSES['manager_type'])[0]
        manager_type_uuid = generate_uuid(manager_type)

        uuid = generate_uuid(str(employee_uuid) + str(org_unit_uuid) + str(responsibility_uuid))

        return Manager.from_simplified_fields(
            uuid=uuid,
            org_unit_uuid=org_unit_uuid,
            person_uuid=employee_uuid,
            responsibility_uuid=responsibility_uuid,
            manager_level_uuid=manager_level_uuid,
            manager_type_uuid=manager_type_uuid,
            from_date="1930-01-01",
            to_date=None,
        )

    return_value = list(list(map(construct_manager, layer)) for layer in org_layers)
    # Ensure all employees were consumed
    assert ilen(employee_iter) == 0
    return return_value


def generate_associations(generate_uuid, employees, org_layers):

    def construct_association(org_unit):
        employee = random.choice(employees)

        employee_uuid = employee.uuid
        org_unit_uuid = org_unit.uuid

        association_type = random.choice(CLASSES['association_type'])[0]
        association_type_uuid = generate_uuid(association_type)

        uuid = generate_uuid(str(employee_uuid) + str(org_unit_uuid) + str(association_type_uuid))

        return Association.from_simplified_fields(
            uuid=uuid,
            org_unit_uuid=org_unit_uuid,
            person_uuid=employee_uuid,
            association_type_uuid=association_type_uuid,
            from_date="1930-01-01",
            to_date=None,
        )

    num_employees_per_org = 5

    def construct_associations(org_unit):
        return [construct_association(org_unit) for i in range(num_employees_per_org)]

    return list(list(flatten(map(construct_associations, layer))) for layer in org_layers)


@click.command()
@click.option(
    "--name",
    help="Name of the root organization",
    required=True,
)
@click.option(
    "--indent", help="Pass 'indent' to json serializer", type=click.INT, default=None
)
@click.option(
    "--lora-file", help="Output Lora Flatfile", type=click.File("w"), required=True
)
@click.option(
    "--mo-file", help="Output OS2mo Flatfile", type=click.File("w"), required=True
)
def generate(name: str, indent: int, lora_file, mo_file) -> None:
    """Flatfile Fixture Generator.

    Used to generate flatfile fixture data (JSON) for OS2mo/LoRa.
    """
    seed = name

    def generate_uuid(identifier):
        return unseeded_generate_uuid(seed + identifier)

    organisation = Organisation.from_simplified_fields(
        uuid=generate_uuid(""),
        name=name,
        user_key=name,
    )
    facets, klasses = generate_facets_and_classes(generate_uuid, organisation)
    # lora_flatfile needs klassifikation
    # lora_flatfile needs itsystems
    lora_flatfile = LoraFlatFileFormat(
        chunks=[
            LoraFlatFileFormatChunk(organisation=organisation),
            LoraFlatFileFormatChunk(
                facetter=facets,
            ),
            LoraFlatFileFormatChunk(klasser=klasses),
        ],
    )

    org_tree = gen_org_tree(seed)

    org_layers = generate_org_units(generate_uuid, org_tree)
    org_address_layers = generate_org_addresses(generate_uuid, seed, org_layers)
    employees = generate_employees(generate_uuid, seed, org_layers)
    employee_addresses = generate_employee_addresses(generate_uuid, seed, employees)
    engagement_layers = generate_engagements(generate_uuid, employees, org_layers)
    manager_layers = generate_managers(generate_uuid, employees, org_layers)
    # TODO: Reactive after: https://git.magenta.dk/rammearkitektur/ra-data-models/-/merge_requests/28
    # association_layers = generate_associations(generate_uuid, employees, org_layers)
    association_layers = []

    # All employee addresses can be merged into the first layer of org-addresses,
    # as employees is a flat layer structure.
    address_layers = list(map(apply(add), zip_longest(org_address_layers, [employee_addresses], fillvalue=[])))

    # mo_flatfile needs it
    # mo_flatfile needs role
    # mo_flatfile needs leave
    mo_flatfile = MOFlatFileFormat(
        chunks=list(map(
            apply(lambda org_layer, employee_layer, address_layer, engagement_layer, manager_layer, association_layer: MOFlatFileFormatChunk(
                org_units=org_layer,
                address=address_layer,
                employees=employee_layer,
                engagements=engagement_layer,
                manager=manager_layer
            )),
            zip_longest(
                org_layers,
                [employees],
                # Offset the following by one, by prepending an empty list.
                # This ensures that their dependencies (i.e. org_units and employees)
                # have been created in the chunk, before they are needed
                prepend([], address_layers),
                prepend([], engagement_layers),
                prepend([], manager_layers),
                prepend([], association_layers),
                fillvalue=[]
            )
        ))
    )
    lora_file.write(lora_flatfile.json(indent=indent))
    mo_file.write(mo_flatfile.json(indent=indent))


if __name__ == "__main__":
    generate(auto_envvar_prefix="FIXTURE_GENERATOR")
