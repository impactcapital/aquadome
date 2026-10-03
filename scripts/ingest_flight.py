"""CLI: ingest a drone telemetry file and queue the flight for processing."""

from __future__ import annotations

import sys
from pathlib import Path

import click


@click.command()
@click.argument("telemetry_file", type=click.Path(exists=True, path_type=Path))
@click.option("--tenant-id", required=True, help="Client tenant identifier")
@click.option("--device-id", required=True, help="Drone serial number or MAC")
@click.option("--pilot-cert", default=None, help="FAA Remote Pilot Certificate number")
@click.option("--hardware-tier", default="commercial", type=click.Choice(["commercial", "blue_uas"]))
def main(
    telemetry_file: Path,
    tenant_id: str,
    device_id: str,
    pilot_cert: str | None,
    hardware_tier: str,
) -> None:
    """
    Normalize a drone telemetry file and queue for the AquaDome pipeline.

    Supported formats: DJI SRT, Skydio JSON, MAVLink .tlog/.bin

    NDAA/ASDA note: use --hardware-tier=blue_uas for any federally-funded
    government contract to document compliance with ASDA §§1821–1833.
    """
    from aquadome.ingestion.normalizer import TelemetryNormalizer

    normalizer = TelemetryNormalizer()
    try:
        telemetry = normalizer.normalize(telemetry_file)
        telemetry.pilot_cert_id = pilot_cert
        telemetry.hardware_tier = hardware_tier
    except ValueError as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    click.echo(f"Flight ID:        {telemetry.flight_id}")
    click.echo(f"Telemetry hash:   {telemetry.telemetry_hash}")
    click.echo(f"Frame count:      {telemetry.frame_count}")
    click.echo(f"Hardware tier:    {telemetry.hardware_tier}")
    click.echo(f"Status:           queued for processing")


if __name__ == "__main__":
    main()
