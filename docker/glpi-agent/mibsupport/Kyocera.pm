package GLPI::Agent::SNMP::MibSupport::Kyocera;

use strict;
use warnings;

use parent 'GLPI::Agent::SNMP::MibSupportTemplate';

use GLPI::Agent::Tools;
use GLPI::Agent::Tools::SNMP;

use constant priority => 7;

use constant kyocera    => '.1.3.6.1.4.1.1347';
use constant sysName    => kyocera . '.40.10.1.1.5.1';

use constant kyoceraPrinter => kyocera . '.41';

# KMCOMMON-MIB
use constant kmCommon           => kyocera . '.42';
use constant kmMedia            => kmCommon . '.2.1';
use constant kmMediaName        => kmMedia . '.1.1.2';
use constant kmMediaCounterItem => kmMedia . '.1.1.6';

our $mibSupport = [
    {
        name        => "kyocera",
        sysobjectid => getRegexpOidMatch(kyoceraPrinter)
    }
];

sub getSnmpHostname {
    my ($self) = @_;

    return getCanonicalString($self->get(sysName));
}

sub run {
    my ($self) = @_;

    my $device = $self->device
        or return;

    my $names = $self->walk(kmMediaName)
        or return;
    my $counters = $self->walk(kmMediaCounterItem)
        or return;

    foreach my $counter (sort keys(%{$names})) {
        my $count = $counters->{$counter}
            or next;
        my $name = "PRINT_".uc($names->{$counter});
        $device->{PAGECOUNTERS}->{$name} = $count;
    }
}

1;

__END__

=head1 NAME

GLPI::Agent::SNMP::MibSupport::Kyocera - Inventory module for Kyocera printers

=head1 DESCRIPTION

This module enhances Kyocera printers support.
