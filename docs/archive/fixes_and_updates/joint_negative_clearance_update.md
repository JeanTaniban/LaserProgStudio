# Joint builder negative clearance update

The joint builder now accepts negative `Clearance` values.

Behavior:

- positive clearance enlarges the female slot and gives mechanical play;
- zero clearance keeps the female slot nominally equal to the male tab;
- negative clearance shrinks the female slot and creates an interference/tighter fit.

The Qt panel range for `Clearance` is now `-100 mm` to `100 mm`. The computational core no longer clamps clearance to zero. Instead, it rejects values that would make the generated female boolean slot smaller than `0.2 mm`, which avoids silently creating unusable geometry.
