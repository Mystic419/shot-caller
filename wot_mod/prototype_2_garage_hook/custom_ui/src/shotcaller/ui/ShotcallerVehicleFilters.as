package shotcaller.ui {
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.geom.Rectangle;
    import flash.text.TextField;
    import flash.text.TextFieldType;
    import flash.text.TextFormat;
    import net.wg.infrastructure.base.AbstractView;

    public final class ShotcallerVehicleFilters extends AbstractView {
        // Two deliberate selector rows: tiers, then all five vehicle classes.
        // The viewport starts below both rows with an 8px breathing gap.
        private const W:Number = 520, H:Number = 680, TOP:Number = 194, BODY_H:Number = 400;
        private var info:TextField, diagnostic:TextField, search:TextField, viewport:Sprite, list:Sprite, thumb:Sprite, wheelCapture:Sprite;
        private var payload:Object, catalogs:Object = {}, hidden:Object = {"6":{}, "8":{}, "10":{}}, classes:Object = {"heavyTank":true,"mediumTank":true,"lightTank":true,"AT-SPG":true,"SPG":true};
        private var currentTier:int = 8, dragging:Boolean = false, dragDX:Number, dragDY:Number;
        public var onClose:Function, onSave:Function, onCancel:Function, onTier:Function, onDefaults:Function, onPayloadDiagnostic:Function;
        public function ShotcallerVehicleFilters(){ addEventListener(Event.ADDED_TO_STAGE, added); trace("[shotcaller] filters constructor"); }
        override protected function onPopulate():void { super.onPopulate(); trace("[shotcaller] filters populate"); }
        override protected function onDispose():void { if(viewport!=null)viewport.removeEventListener(MouseEvent.MOUSE_WHEEL,wheel); stopDragListeners(); super.onDispose(); }
        private function added(e:Event):void { removeEventListener(Event.ADDED_TO_STAGE,added); build(); }
        private function build():void {
            graphics.beginFill(0x171914,.98);graphics.drawRect(0,0,W,H);graphics.endFill();graphics.lineStyle(1,0x625B48);graphics.drawRect(.5,.5,W-1,H-1);graphics.beginFill(0x2C2F28);graphics.drawRect(4,4,W-8,30);graphics.endFill();graphics.beginFill(0xD98B34);graphics.drawRect(5,33,W-10,1);graphics.endFill();
            label("ShotCaller vehicle filters",16,8,W-80,24,16,0xE8E2D5,true); button("Close",452,3,54,28);
            info=label("Checked vehicles are hidden from ShotCaller results.",16,44,W-32,24,12,0xB8B1A3,false);
            diagnostic=label("Waiting for catalog...",16,66,W-32,20,13,0xF0A64B,true);
            label("Search:",16,94,54,20,12,0xFFFFFF,false); search=label("",72,91,250,25,13,0xFFFFFF,false);search.type=TextFieldType.INPUT;search.selectable=true;search.mouseEnabled=true;search.background=true;search.backgroundColor=0x222222;search.border=true;search.borderColor=0x666666;search.addEventListener(Event.CHANGE,changed);
            // Tier selector row.
            button("VI",16,124,54,28);button("VIII",76,124,54,28);button("X",136,124,54,28);
            // Vehicle-class row: fixed 6px gutters, aligned to the same 16px
            // content inset, and sized so Tank Destroyer remains unwrapped.
            button("Heavy",16,158,74,28);button("Medium",96,158,78,28);button("Light",180,158,64,28);button("Tank Destroyer",250,158,146,28);button("Artillery",402,158,94,28);
            viewport=new Sprite();viewport.x=16;viewport.y=TOP;viewport.scrollRect=new Rectangle(0,0,W-54,BODY_H);addChild(viewport);
            // Scaleform does not hit-test an empty Sprite gap. This near-zero
            // alpha rectangle sits behind rows, so its wheel event bubbles to
            // the one authoritative viewport handler without blocking clicks.
            wheelCapture=new Sprite();wheelCapture.mouseEnabled=true;wheelCapture.mouseChildren=false;wheelCapture.graphics.beginFill(0x000000,0.01);wheelCapture.graphics.drawRect(0,0,W-54,BODY_H);wheelCapture.graphics.endFill();viewport.addChild(wheelCapture);
            list=new Sprite();viewport.addChild(list);viewport.addEventListener(MouseEvent.MOUSE_WHEEL,wheel);
            graphics.beginFill(0x292929);graphics.drawRect(W-24,TOP,8,BODY_H);graphics.endFill();thumb=new Sprite();thumb.graphics.beginFill(0xAAAAAA);thumb.graphics.drawRect(0,0,8,50);thumb.graphics.endFill();thumb.x=W-24;thumb.y=TOP;thumb.addEventListener(MouseEvent.MOUSE_DOWN,thumbDown);addChild(thumb);
            button("Hide All",16,620,82,30);button("Show All",104,620,82,30);button("Defaults",192,620,82,30);button("Save",350,620,72,30);button("Cancel",428,620,72,30); addEventListener(MouseEvent.MOUSE_DOWN,titleDown);
        }
        private function label(s:String,xv:Number,yv:Number,w:Number,h:Number,size:Number,color:uint,bold:Boolean):TextField {var t:TextField=new TextField();t.x=xv;t.y=yv;t.width=w;t.height=h;t.multiline=true;t.wordWrap=true;t.selectable=false;t.defaultTextFormat=new TextFormat("$TextFont",size,color,bold);t.text=s;addChild(t);return t;}
        private function button(s:String,xv:Number,yv:Number,w:Number,h:Number):void {var b:Sprite=new Sprite();b.name=s;b.x=xv;b.y=yv;b.graphics.beginFill(0x34372F);b.graphics.drawRect(0,0,w,h);b.graphics.endFill();b.graphics.lineStyle(1,0x8A7958);b.graphics.drawRect(.5,.5,w-1,h-1);var t:TextField=new TextField();t.width=w;t.height=h-2;t.y=4;t.selectable=false;t.mouseEnabled=false;t.defaultTextFormat=new TextFormat("$TextFont",12,0xE8E2D5,true,null,null,null,null,"center");t.text=s;b.addChild(t);b.addEventListener(MouseEvent.CLICK,click);addChild(b);}
        private var received:int = 0, rejected:int = 0;
        private function payloadLog(message:String):void { trace("[shotcaller] filter payload diagnostic: "+message); if(onPayloadDiagnostic!=null)onPayloadDiagnostic(message); }
        private function payloadFail(stage:String):void {diagnostic.text=stage;payloadLog("failure="+stage);clearList();}
        private function validNative(id:*, name:*, kind:*, expectedTier:int):Boolean {var c:String=String(kind);return !isNaN(Number(id)) && Number(id)>0 && String(name).length>0 && (c=="heavyTank"||c=="mediumTank"||c=="lightTank"||c=="AT-SPG"||c=="SPG");}
        public function as_beginData(selectedTier:*, notice:String):void {catalogs={"6":[],"8":[],"10":[]};hidden={"6":{},"8":{},"10":{}};received=0;rejected=0;currentTier=int(selectedTier);if(currentTier!=6&&currentTier!=8&&currentTier!=10)currentTier=8;info.text=notice;payloadLog("parser=native_daapi_arrays begin data received tier="+currentTier);}
        public function as_setTierCatalog(tier:*, ids:*, names:*, classesData:*):void {var key:String=String(int(tier));if(key!="6"&&key!="8"&&key!="10"){payloadFail("Invalid tier catalog.");return;}if(!(ids is Array)||!(names is Array)||!(classesData is Array)){payloadFail("Tier "+key+" arrays missing.");return;}var count:int=Math.min((ids as Array).length,Math.min((names as Array).length,(classesData as Array).length));var grouped:Object={},raw:int=0;for(var i:int=0;i<count;i++){if(validNative(ids[i],names[i],classesData[i],int(key))){raw++;var normalized:String=String(names[i]).toLowerCase()+"|"+String(classesData[i]).toLowerCase();var row:Object=grouped[normalized];if(row==null){row={"tier":int(key),"name":String(names[i]),"class":String(classesData[i]),"ids":[]};grouped[normalized]=row;}row.ids.push(Number(ids[i]));received++;}else rejected++;}var output:Array=[];for each(var groupedRow:Object in grouped)output.push(groupedRow);output.sortOn("name",Array.CASEINSENSITIVE);catalogs[key]=output;payloadLog("tier "+key+" received raw="+raw+" grouped="+output.length+" duplicateRowsRemoved="+(raw-output.length));for each(var sample:Object in output)if(sample.ids.length>1){payloadLog("grouped name="+sample.name+" class="+sample["class"]+" ids="+sample.ids.length);break;}}
        public function as_setHiddenIds(tier:*, ids:*):void {var key:String=String(int(tier)),set:Object={};if((key!="6"&&key!="8"&&key!="10")||!(ids is Array))return;for each(var id:* in ids)if(!isNaN(Number(id))&&Number(id)>0)set[String(Number(id))]=true;hidden[key]=set;var checked:int=0;for each(var row:Object in catalogs[key] as Array)if(rowChecked(row))checked++;payloadLog("hidden tier="+key+" received count="+(ids as Array).length+" grouped checked rows tier="+key+" count="+checked);}
        public function as_finishData():void {var six:Array=catalogs["6"] as Array,eight:Array=catalogs["8"] as Array,ten:Array=catalogs["10"] as Array;if(six==null||eight==null||ten==null){payloadFail("Tier catalog missing.");return;}payloadLog("parse success tier6="+six.length+" tier8="+eight.length+" tier10="+ten.length+" accepted="+received+" skipped="+rejected);render();}
        private function vehicles():Array {var value:* = catalogs[String(currentTier)]; return value is Array ? value as Array : [];}
        private function rowMatches(v:Object):Boolean {var q:String=search==null?"":search.text.toLowerCase();return classes[String(v["class"])]===true && (q=="" || String(v.name).toLowerCase().indexOf(q)>=0);}
        private function rowChecked(row:Object):Boolean {var set:Object=hidden[String(row.tier)];for each(var id:* in row.ids)if(set[String(Number(id))]!==true)return false;return row.ids.length>0;}
        private function setRowChecked(row:Object, checked:Boolean):void {var set:Object=hidden[String(row.tier)];for each(var id:* in row.ids){if(checked)set[String(Number(id))]=true;else delete set[String(Number(id))];}}
        private function hiddenIDs(key:String):Array {var output:Array=[],set:Object=hidden[key];for(var id:String in set)if(set[id]===true)output.push(Number(id));output.sort(Array.NUMERIC);return output;}
        private function clearList():void {if(list==null)return;while(list.numChildren>0){var child:VehicleFilterRow=list.getChildAt(0) as VehicleFilterRow;if(child!=null)child.removeEventListener(MouseEvent.CLICK,rowClick);list.removeChildAt(0);}}
        private function render():void {if(list==null)return;clearList();var all:Array=vehicles(), shown:int=0,yv:Number=0;payloadLog("render started tier="+currentTier+" groupedRows="+all.length);for each(var v:Object in all){if(!rowMatches(v))continue;shown++;var r:VehicleFilterRow=new VehicleFilterRow();r.tier=int(v.tier);r.vehicleName=String(v.name);r.vehicleClass=String(v["class"]);r.vehicleIds=v.ids as Array;r.groupedData=v;r.y=yv;r.graphics.beginFill(rowChecked(v)?0x3C3524:(shown%2?0x20231C:0x1A1C17));r.graphics.drawRect(0,0,W-58,26);r.graphics.endFill();var t:TextField=new TextField();t.x=8;t.y=4;t.width=W-72;t.height=21;t.selectable=false;t.mouseEnabled=false;t.defaultTextFormat=new TextFormat("$TextFont",13,0xE8E2D5,false);t.text=(rowChecked(v)?"[x] ":"[ ] ")+v.name+"   "+v["class"];r.addChild(t);r.addEventListener(MouseEvent.CLICK,rowClick);list.addChild(r);if(shown==1)payloadLog("row metadata bound name="+r.vehicleName+" ids="+r.vehicleIds.length);yv+=28;}if(shown==0){var empty:TextField=label("No vehicles match the current tier, search, and class filters.",0,0,W-58,40,13,0xB8B1A3,false);list.addChild(empty);}list.y=0;diagnostic.text="Loaded "+all.length+" Tier "+roman(currentTier)+" vehicles; showing "+shown+".";updateScroll();payloadLog("render completed visibleRows="+shown);}
        private function roman(t:int):String{return t==6?"VI":(t==8?"VIII":"X");}
        private function changed(e:Event):void{render();}
        private function rowClick(e:MouseEvent):void{var display:VehicleFilterRow=e.currentTarget as VehicleFilterRow;var row:Object=display==null?null:display.groupedData;if(row==null)return;var checked:Boolean=!rowChecked(row);setRowChecked(row,checked);payloadLog("row clicked name="+display.vehicleName+" checked="+checked+" ids="+display.vehicleIds.length);render();}
        private function wheel(e:MouseEvent):void{list.y=Math.min(0,Math.max(-(Math.max(0,list.height-BODY_H)),list.y+e.delta*24));updateThumb();}
        private function updateScroll():void{thumb.visible=list.height>BODY_H;updateThumb();}
        private function updateThumb():void{if(!thumb.visible)return;thumb.height=Math.max(28,BODY_H*BODY_H/Math.max(1,list.height));thumb.y=TOP+(-list.y/Math.max(1,list.height-BODY_H))*(BODY_H-thumb.height);}
        private function thumbDown(e:MouseEvent):void{stage.addEventListener(MouseEvent.MOUSE_MOVE,thumbMove);stage.addEventListener(MouseEvent.MOUSE_UP,thumbUp);}
        private function thumbMove(e:MouseEvent):void{thumb.y=Math.max(TOP,Math.min(TOP+BODY_H-thumb.height,mouseY));list.y=-(thumb.y-TOP)/Math.max(1,BODY_H-thumb.height)*Math.max(0,list.height-BODY_H);}
        private function thumbUp(e:MouseEvent):void{stage.removeEventListener(MouseEvent.MOUSE_MOVE,thumbMove);stage.removeEventListener(MouseEvent.MOUSE_UP,thumbUp);}
        private function click(e:MouseEvent):void{var a:String=e.currentTarget.name;if(a=="VI"||a=="VIII"||a=="X"){currentTier=a=="VI"?6:(a=="VIII"?8:10);if(onTier!=null)onTier(currentTier);render();}else if(a=="Heavy"||a=="Medium"||a=="Light"||a=="Tank Destroyer"||a=="Artillery"){var k:String=a=="Heavy"?"heavyTank":(a=="Medium"?"mediumTank":(a=="Light"?"lightTank":(a=="Tank Destroyer"?"AT-SPG":"SPG")));classes[k]=!classes[k];render();}else if(a=="Hide All"||a=="Show All"){var rows:int=0,ids:int=0;for each(var v:Object in vehicles())if(rowMatches(v)){rows++;ids+=v.ids.length;setRowChecked(v,a=="Hide All");}payloadLog((a=="Hide All"?"hide all applied ":"show all applied ")+"tier="+currentTier+" rows="+rows+" ids="+ids);render();}else if(a=="Defaults"){hidden={"6":{},"8":{},"10":{}};payloadLog("defaults applied tier6=0 tier8=0 tier10=0");if(onDefaults!=null)onDefaults();render();}else if(a=="Save"&&onSave!=null){var six:Array=hiddenIDs("6"),eight:Array=hiddenIDs("8"),ten:Array=hiddenIDs("10");payloadLog("filter save preparing: tier6="+six.length+" tier8="+eight.length+" tier10="+ten.length+" firstTier8Ids="+eight.slice(0,5).join(","));onSave(six,eight,ten);}else if(a=="Cancel"&&onCancel!=null)onCancel();else if(a=="Close"&&onClose!=null)onClose();}
        private function titleDown(e:MouseEvent):void{if(mouseY>36 || e.target.name=="Close")return;dragging=true;dragDX=mouseX;dragDY=mouseY;stage.addEventListener(MouseEvent.MOUSE_MOVE,titleMove);stage.addEventListener(MouseEvent.MOUSE_UP,titleUp);}
        private function titleMove(e:MouseEvent):void{if(!dragging)return;x=Math.max(0,Math.min(stage.stageWidth-W,stage.mouseX-dragDX));y=Math.max(0,Math.min(stage.stageHeight-H,stage.mouseY-dragDY));}
        private function titleUp(e:MouseEvent):void{dragging=false;stopDragListeners();}
        private function stopDragListeners():void{if(stage!=null){stage.removeEventListener(MouseEvent.MOUSE_MOVE,titleMove);stage.removeEventListener(MouseEvent.MOUSE_UP,titleUp);}}
    }
}
