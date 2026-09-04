package GLPI::Agent::SNMP::MibSupport::Konica;

use strict;
use warnings;

use parent 'GLPI::Agent::SNMP::MibSupportTemplate';

use GLPI::Agent::Tools;
use GLPI::Agent::Tools::SNMP;

use constant    enterprises => '.1.3.6.1.4.1';
use constant    konica      => enterprises . '.18334';

use constant    konicaSysobjectID   => konica . '.1.1.1.2';

use constant    konicaModel             => konica . '.1.1.1.1.6.2.1.0';

use constant    konicaPrinterCounters   => konica . '.1.1.1.5.7.2';

use constant    konicaTotal         => konicaPrinterCounters . '.1.1.0';
use constant    konicaRectoVerso    => konicaPrinterCounters . '.1.3.0';
use constant    konicaBlackCopy     => konicaPrinterCounters . '.2.1.5.1.1';
use constant    konicaBlackPrint    => konicaPrinterCounters . '.2.1.5.1.2';
use constant    konicaColorCopy     => konicaPrinterCounters . '.2.1.5.2.1';
use constant    konicaColorPrint    => konicaPrinterCounters . '.2.1.5.2.2';
use constant    konicaScans         => konicaPrinterCounters . '.3.1.5.1';
use constant    konicaA3Print       => konicaPrinterCounters . '.4.1.5.1.14'; # BW A3 counter
use constant    konicaA4Print       => konicaPrinterCounters . '.4.1.5.1.15'; # BW A4 counter

use constant    konicaFirmware          => konica . '.1.1.1.5.5.1.1';
use constant    konicaFirmwareName      => konicaFirmware . '.2';
use constant    konicaFirmwareVersion   => konicaFirmware . '.3';

our $mibSupport = [
    {
        name        => "konica-exact",
        sysobjectid => getRegexpOidMatch('.1.3.6.1.4.1.18334.1.2.1.2.1.217.2.1'),
    },
    {
        name        => "konica-1-2-branch",
        sysobjectid => getRegexpOidMatch(konica . '.1.2'),
    },
    {
        name        => "konica-printer",
        sysobjectid => getRegexpOidMatch(konicaSysobjectID),
    },
];

sub getModel {
    my ($self) = @_;

    my $model = getCanonicalString(hex2char($self->get(konicaModel)))
        or return;

    # Strip manufacturer
    $model =~ s/^KONICA MINOLTA\s+//i;

    return $model;
}

sub run {
    my ($self) = @_;

    my $device = $self->device
        or return;

    # Retrieve key counters
    my $total_pages  = $self->get(konicaTotal) // 0;
    my $color_print  = $self->get(konicaColorPrint) // 0;
    my $black_print  = $self->get(konicaBlackPrint) // 0;
    my $color_copy   = $self->get(konicaColorCopy) // 0;
    my $black_copy   = $self->get(konicaBlackCopy) // 0;
    my $scans        = $self->get(konicaScans) // 0;
    my $bw_a3        = $self->get(konicaA3Print) // 0;
    my $bw_a4        = $self->get(konicaA4Print) // 0;

    # Initialize PAGECOUNTERS with page counters including BW A3/A4
    $device->{PAGECOUNTERS} = {
        TOTAL       => $total_pages,
        PRINTCOLOR  => $color_print,
        PRINTBLACK  => $black_print,
        COPYCOLOR   => $color_copy,
        COPYBLACK   => $black_copy,
        SCANNED     => $scans,
        RECTOVERSO  => $self->get(konicaRectoVerso) // 0,
        BW_A3       => $bw_a3,
        BW_A4       => $bw_a4,
    };

    # Set PRINTTOTAL if print found and no dedicated counter is defined
    if ($device->{PAGECOUNTERS}->{PRINTCOLOR} || $device->{PAGECOUNTERS}->{PRINTBLACK}) {
        $device->{PAGECOUNTERS}->{PRINTTOTAL} =
            ($device->{PAGECOUNTERS}->{PRINTBLACK} // 0) + ($device->{PAGECOUNTERS}->{PRINTCOLOR} // 0);
    }

    # Set COPYTOTAL if copy found and no dedicated counter is defined
    if ($device->{PAGECOUNTERS}->{COPYCOLOR} || $device->{PAGECOUNTERS}->{COPYBLACK}) {
        $device->{PAGECOUNTERS}->{COPYTOTAL} =
            ($device->{PAGECOUNTERS}->{COPYBLACK} // 0) + ($device->{PAGECOUNTERS}->{COPYCOLOR} // 0);
    }

    my $firmwareName    = $self->walk(konicaFirmwareName);
    my $firmwareVersion = $self->walk(konicaFirmwareVersion);
    if ($firmwareName && $firmwareVersion) {
        foreach my $key (keys(%{$firmwareName})) {
            my $name = getCanonicalString(hex2char($firmwareName->{$key}))
                or next;
            my $version = getCanonicalString(hex2char($firmwareVersion->{$key}))
                or next;
            next if $version eq '-' || $version eq "Registered";

            # Strip version string at the end of name
            $name =~ s/\s+version$//i;

            my $firmware = {
                NAME            => "Konica $name",
                DESCRIPTION     => "Printer $name",
                TYPE            => "printer",
                VERSION         => $version,
                MANUFACTURER    => "Konica"
            };
            $device->addFirmware($firmware);
        }
    }
}

1;

__END__

=head1 NAME

GLPI::Agent::SNMP::MibSupport::Konica - Inventory module for Konica Printers

=head1 DESCRIPTION

The module enhances Konica printers devices support, including black-and-white A3 and A4 format page counters.
