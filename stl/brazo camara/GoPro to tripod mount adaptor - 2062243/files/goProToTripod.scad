//GoPro to Tripod Mount

goPro_FinSpacing = 3.45;
goPro_FinWidth = 2.95;
goPro_MountThreeFinWidth = goPro_FinSpacing * 2 + goPro_FinWidth * 3;
goPro_MountTwoFinWidth = goPro_FinWidth * 3;

quarterTwentyNut_Radius = hexagonRadiusFromWidth(11.25);
quarterTwentyNut_Height = 5.6;
quarterTwentyBoltHead_Height = 4.3;

quarterTwenty_outerRadius = 3.25;

M5_outerRadius = 5.3 / 2;
M5Nut_Radius = hexagonRadiusFromWidth(8.0);

adaptor_Width = goPro_FinSpacing * 2 + goPro_FinWidth * 3;

goProToTripod(fins = "three");
//thumbScrew();

module thumbScrew() {
    difference() {
      cylinder( r = 15, h = quarterTwentyNut_Height + 2, $fn = 128 );
      translate([0,0,-1])
      cylinder( r = quarterTwenty_outerRadius + 1.0, h = quarterTwentyNut_Height + 3, $fn = 64 );
      translate([0, 0, 2]) {
        cylinder( r = quarterTwentyNut_Radius, h = quarterTwentyNut_Height, $fn = 6 );
      }    
      
      for( angle = [0:6]) {
        rotate([ 0, 0, angle * 60])
        translate( [33, 0, 0] )
          cylinder( r = 20, h = quarterTwentyNut_Height + 2, $fn = 64 );
      }
    }
}

module goProToTripod(fins = "three") {
  difference() {
    union() {
      cube([12, adaptor_Width, 16]);
      translate([12 + 8,0,8])
      rotate([0,-90,0]) {
        if( fins == "three" ) {
          goProThreeFinMount(wid = goPro_FinWidth, spacing = goPro_FinSpacing);
        } else {
          translate([ 0, goPro_FinWidth, 0 ])
            goProTwoFinMount(wid = goPro_FinWidth, spacing = goPro_FinSpacing);         
        }
      }
    }
    
    translate( [(12 - quarterTwentyBoltHead_Height) / 2, adaptor_Width / 2, quarterTwentyNut_Radius + 1]) {
      rotate([0,90,0]) 
      hull() {
        cylinder( r = quarterTwentyNut_Radius, h = quarterTwentyBoltHead_Height, $fn = 6 );
        translate( [-10, 0, 0] )
          cylinder( r = quarterTwentyNut_Radius, h = quarterTwentyBoltHead_Height, $fn = 6 );       
      }
      
      rotate([0,-90,0])
      hull() {
        cylinder( r = quarterTwenty_outerRadius, h = 10, $fn = 64 );
        translate( [10, 0, 0] )
          cylinder( r = quarterTwenty_outerRadius, h = 10, $fn = 64 );        
      } 
    }
  }
}

module goProThreeFinMount(wid = 3.0, spacing = 3.3) {
  goProFin(wid);
  for( i = [1:2]) {
    translate([0, (spacing + wid) * i, 0])
      goProFin(wid);   
  }

  translate([0, spacing * 2 + wid * 3, 0]) 
  rotate([-90, 0, 0]) 
  difference() { 
    cylinder(r1 = 8, r2 = 5, h = 3.2, $fn = 64);
    translate([0,0,-2])
      cylinder( r = M5_outerRadius, h = wid + 1, $fn = 64 );
    translate([0,0,1])
      cylinder(r = M5Nut_Radius, h = 3.5, $fn = 6);
  }
}

module goProTwoFinMount(wid = 3.0, spacing = 3.3) {
  goProFin(wid);
  translate([0, wid + spacing, 0])
    goProFin(wid); 
}

module goProFin(wid = 3.0) {
  translate([0, wid, 0])
  difference() {
    union() {
      translate([ -8, -wid, 0])
        cube([ 16, wid, 8]);
      rotate([ 90, 0, 0 ])
        cylinder( r = 8.0, h = wid, $fn = 64 );      
    }
    translate([0, 0.5, 0])
    rotate([ 90, 0, 0 ])
      cylinder( r = M5_outerRadius, h = wid + 1, $fn = 64 );
  }
}

module tripodMount(wid = quarterTwentyNut_Radius + 10) {
  outerRadius = hexagonRadiusFromWidth(wid);
  rotate( [0, 0, 30])
  difference() {
    cylinder( r = outerRadius, h = quarterTwentyNut_Height, $fn = 6 );
    cylinder( r = quarterTwentyNut_Radius, h = quarterTwentyNut_Height, $fn = 6 );
  }
}

function hexagonRadiusFromWidth( w ) = (w) / sqrt(3);