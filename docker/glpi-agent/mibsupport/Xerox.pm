package GLPI::Agent::SNMP::MibSupport::Xerox;

use strict;
use warnings;

use parent 'GLPI::Agent::SNMP::MibSupportTemplate';

use GLPI::Agent::Tools;
use GLPI::Agent::Tools::SNMP;

use constant    enterprises => '.1.3.6.1.4.1';

use constant    xerox            => enterprises . '.253';
use constant    xeroxCommonMIB   => xerox . '.8';
use constant    xcmHrDevDetailEntry => xeroxCommonMIB . '.53.13.2.1';

# Printing counters
use constant    xeroxTotalPrint      => xcmHrDevDetailEntry . '.6.1.20.1';  # PRINTTOTAL
use constant    xeroxColorPrint      => xcmHrDevDetailEntry . '.6.1.20.33'; # PRINTCOLOR
use constant    xeroxBlackPrint      => xcmHrDevDetailEntry . '.6.1.20.34'; # PRINTBLACK
use constant    xeroxColorA3Print    => xcmHrDevDetailEntry . '.6.1.20.43'; # per-format A3 color
use constant    xeroxBlackA3Print    => xcmHrDevDetailEntry . '.6.1.20.44'; # per-format A3 black

# Copy and Scan counters
use constant    xeroxColorCopy       => xcmHrDevDetailEntry . '.6.11.20.25';
use constant    xeroxBlackCopy       => xcmHrDevDetailEntry . '.6.11.20.3';
use constant    xeroxScanSentByEmail => xcmHrDevDetailEntry . '.6.10.20.11';
use constant    xeroxScanSavedOnNetwork => xcmHrDevDetailEntry . '.6.10.20.12';

our $mibSupport = [
    {
        name        => "xerox-printer",
        sysobjectid => getRegexpOidMatch(xeroxCommonMIB)
    }
];

sub run {
    my ($self) = @_;

    my $device = $self->device
        or return;

    # Retrieve key counters
    my $total_pages = $self->get(xeroxTotalPrint) // 0;
    my $color_total = $self->get(xeroxColorPrint) // 0;
    my $black_total = $self->get(xeroxBlackPrint) // 0;
    my $color_a3    = $self->get(xeroxColorA3Print) // 0;
    my $black_a3    = $self->get(xeroxBlackA3Print) // 0;

    # Calculate A4 per-format values
    my $color_a4 = $color_total - $color_a3;
    my $black_a4 = $black_total - $black_a3;
    $color_a4 = 0 if $color_a4 < 0;
    $black_a4 = 0 if $black_a4 < 0;

    # Initialize PAGECOUNTERS with page counters including PRINTCOLOR
    $device->{PAGECOUNTERS} = {
        PRINTCOLOR => $color_total,
        BW_A3      => $black_a3,
        BW_A4      => $black_a4,
        COLOR_A3   => $color_a3,
        COLOR_A4   => $color_a4,
        TOTAL      => $total_pages,
    };

    # Additional mapping for copy and scanned counters
    my %mapping = (
        COPYCOLOR => xeroxColorCopy,
        COPYBLACK => xeroxBlackCopy,
        SCANNED   => [ xeroxScanSentByEmail, xeroxScanSavedOnNetwork ],
    );

    foreach my $counter (sort keys %mapping) {
        my $count = 0;
        if (ref $mapping{$counter} eq 'ARRAY') {
            $count += $self->get($_) // 0 for @{ $mapping{$counter} };
        } else {
            $count = $self->get($mapping{$counter}) // 0;
        }
        next unless $count;
        $device->{PAGECOUNTERS}->{$counter} = $count;
    }

    # Compute COPYTOTAL if needed
    if ($device->{PAGECOUNTERS}->{COPYCOLOR} || $device->{PAGECOUNTERS}->{COPYBLACK}) {
        $device->{PAGECOUNTERS}->{COPYTOTAL} = 
            ($device->{PAGECOUNTERS}->{COPYBLACK} // 0) + ($device->{PAGECOUNTERS}->{COPYCOLOR} // 0);
    }
}

1;