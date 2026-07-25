package shotcaller.ui {
    import flash.display.Sprite;

    /** Sealed Scaleform-safe row metadata; never attach arbitrary fields to Sprite. */
    public final class VehicleFilterRow extends Sprite {
        public var tier:int;
        public var vehicleName:String;
        public var vehicleClass:String;
        public var vehicleIds:Array;
        public var groupedData:Object;

        public function VehicleFilterRow() {
            vehicleIds = [];
        }
    }
}
